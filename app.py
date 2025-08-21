import streamlit as st
import cv2
import pandas as pd
import numpy as np
import tempfile
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import easyocr
import re
import gc

st.title("⚾ 手書きスコアOCR（Community Cloud 安定版）")

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
# EasyOCR 初期化（1回だけ）
# -----------------------------
@st.cache_resource
def get_reader():
    return easyocr.Reader(['ja'], gpu=False)
reader = get_reader()

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
    # 前処理: ノイズ除去・コントラスト強化・傾き補正
    # -----------------------------
    gray = cv2.medianBlur(gray, 3)
    gray = cv2.equalizeHist(gray)

    # 最大幅を1000pxに制限（Community Cloud向け）
    h, w = gray.shape
    if w > 1000:
        ratio = 1000 / w
        gray = cv2.resize(gray, (1000, int(h*ratio)), interpolation=cv2.INTER_AREA)
        img = cv2.resize(img, (1000, int(h*ratio)), interpolation=cv2.INTER_AREA)

    # 二値化反転
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
    gray = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    thresh = cv2.warpAffine(thresh, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

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

    st.subheader("検出された列")
    img_disp = img.copy()
    for x1, x2 in column_coords:
        cv2.rectangle(img_disp, (x1,0), (x2,img.shape[0]), (0,255,0), 2)
    st.image(img_disp, use_column_width=True)

    # -----------------------------
    # EasyOCR で列ごと OCR
    # -----------------------------
    rows_data = []
    for idx, (x1, x2) in enumerate(column_coords):
        col_img = gray[:, x1:x2]

        # 列幅が狭い場合は拡大
        if col_img.shape[1] < 200:
            scale = 200 / col_img.shape[1]
            col_img = cv2.resize(col_img, (int(col_img.shape[1]*scale), int(col_img.shape[0]*scale)), interpolation=cv2.INTER_LINEAR)

        # 二値化
        _, col_img = cv2.threshold(col_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # OCR
        result = reader.readtext(col_img, detail=0)
        lines = [line.strip() for line in result if line.strip()]

        # OCR後補正
        corrected = []
        for line in lines:
            if idx == 0:
                # 打順: 数字のみ
                line = re.sub(r'\D', '', line)
            elif idx == 2:
                # 結果: スコア用語のみ
                allowed = ['安打','三振','四球','敬遠','失策','犠打','犠飛']
                if line not in allowed:
                    line = ''
            corrected.append(line)
        rows_data.append(corrected)

        # メモリ解放
        del col_img
        gc.collect()

    # 列ごとに長さを揃える
    max_len = max(len(lst) for lst in rows_data)
    for i in range(len(rows_data)):
        if len(rows_data[i]) < max_len:
            rows_data[i] += [""] * (max_len - len(rows_data[i]))

    df = pd.DataFrame({f"Col{idx+1}": rows_data[idx] for idx in range(len(rows_data))})
    st.subheader("解析結果（最適化版）")
    st.dataframe(df)

    # -----------------------------
    # Googleスプレッドシート登録
    # -----------------------------
    if st.button("Googleスプレッドシートに登録"):
        try:
            client = connect_gsheet()
            sheet = client.open("野球スコア").sheet1
            for _, row in df.iterrows():
                sheet.append_row(row.tolist())
            st.success("✅ 登録完了")
        except Exception as e:
            st.error(f"スプレッドシート登録でエラー: {e}")
