import streamlit as st
import cv2
import pandas as pd
import tempfile
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import easyocr
import re

st.title("⚾ 野球スコアOCR（手書き・精度強化版）")

# -----------------------------
# Google Sheets 認証
# -----------------------------
def connect_gsheet():
    creds_dict = st.secrets["gcp_service_account"]
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# -----------------------------
# 画像アップロード
# -----------------------------
uploaded_file = st.file_uploader("スコアシート画像をアップロードしてください", type=["jpg","jpeg","png"])

if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(uploaded_file.read())
        img_path = tmp.name

    img = cv2.imread(img_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # -----------------------------
    # 前処理: ノイズ除去・コントラスト強化
    # -----------------------------
    gray = cv2.medianBlur(gray, 3)
    gray = cv2.equalizeHist(gray)

    # 二値化（反転）
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # 傾き補正
    coords = np.column_stack(np.where(thresh > 0))
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    (h, w) = thresh.shape[:2]
    M = cv2.getRotationMatrix2D((w//2, h//2), angle, 1.0)
    thresh = cv2.warpAffine(thresh, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    gray = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    # 膨張処理
    kernel = np.ones((2,2), np.uint8)
    thresh = cv2.dilate(thresh, kernel, iterations=1)

    # -----------------------------
    # 列ごと輪郭検出
    # -----------------------------
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    column_coords = []
    for cnt in contours:
        x, y, w_box, h_box = cv2.boundingRect(cnt)
        if w_box > 20 and h_box > 20:
            column_coords.append((x, x + w_box))
    column_coords = sorted(column_coords, key=lambda x: x[0])

    st.subheader("検出された列（輪郭）")
    img_disp = img.copy()
    for x1, x2 in column_coords:
        cv2.rectangle(img_disp, (x1,0), (x2,img.shape[0]), (0,255,0), 2)
    st.image(img_disp, use_column_width=True)

    # -----------------------------
    # EasyOCRで列ごと OCR
    # -----------------------------
    reader = easyocr.Reader(['ja'])
    rows_data = []

    for idx, (x1, x2) in enumerate(column_coords):
        col_img = gray[:, x1:x2]
        # 列ごとリサイズ
        scale_percent = 200
        width = int(col_img.shape[1] * scale_percent / 100)
        height = int(col_img.shape[0] * scale_percent / 100)
        col_img = cv2.resize(col_img, (width, height), interpolation=cv2.INTER_LINEAR)
        _, col_img = cv2.threshold(col_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        result = reader.readtext(col_img, detail=0)
        lines = [line.strip() for line in result if line.strip()]

        # -----------------------------
        # OCR後の簡易補正
        # -----------------------------
        corrected_lines = []
        for i, line in enumerate(lines):
            # 打順は数字のみ
            if idx == 0:
                line = re.sub(r'\D', '', line)
            # 結果はスコア用語のみ残す（例: 安打, 三振, 四球）
            elif idx == 2:
                allowed = ['安打', '三振', '四球', '敬遠', '失策', '犠打', '犠飛']
                if line not in allowed:
                    line = ''
            corrected_lines.append(line)
        rows_data.append(corrected_lines)

    # 列ごとに長さを合わせる
    max_len = max(len(lst) for lst in rows_data)
    for i in range(len(rows_data)):
        if len(rows_data[i]) < max_len:
            rows_data[i] += [""] * (max_len - len(rows_data[i]))

    # 列名
    df = pd.DataFrame({f"Col{idx+1}": rows_data[idx] for idx in range(len(rows_data))})

    st.subheader("解析データ（最適化版）")
    st.dataframe(df)

    # -----------------------------
    # Googleスプレッドシート登録
    # -----------------------------
    if st.button("Googleスプレッドシートに登録"):
        try:
            client = connect_gsheet()
            sheet = client.open("野球スコア").sheet1
            for index, row in df.iterrows():
                sheet.append_row(row.tolist())
            st.success("✅ Googleスプレッドシートに登録しました！")
        except Exception as e:
            st.error(f"Googleスプレッドシート登録でエラー: {e}")
