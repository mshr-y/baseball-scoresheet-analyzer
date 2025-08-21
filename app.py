import streamlit as st
import cv2
import pytesseract
import pandas as pd
import tempfile
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.title("⚾ 野球スコアOCR（手書き・自動列検出版）")

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
    gray = cv2.medianBlur(gray, 3)
    gray = cv2.equalizeHist(gray)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)  # 反転で輪郭検出しやすく

    # 輪郭検出で列を自動検出
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    column_coords = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        # 幅が小さいものは除外
        if w > 20 and h > 20:
            column_coords.append((x, x + w))
    
    # 左から右にソート
    column_coords = sorted(column_coords, key=lambda x: x[0])

    st.subheader("検出された列（輪郭）")
    img_disp = img.copy()
    for x1, x2 in column_coords:
        cv2.rectangle(img_disp, (x1,0), (x2,img.shape[0]), (0,255,0), 2)
    st.image(img_disp, use_column_width=True)

    # -----------------------------
    # 列ごと OCR
    # -----------------------------
    rows_data = []
    custom_config = r'--oem 1 --psm 6'  # LSTM 手書き用

    for idx, (x1, x2) in enumerate(column_coords):
        col_img = gray[:, x1:x2]
        # ノイズ除去・二値化
        col_img = cv2.medianBlur(col_img, 3)
        _, col_img = cv2.threshold(col_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        text = pytesseract.image_to_string(col_img, lang="jpn", config=custom_config)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        rows_data.append(lines)

    # 列ごとに長さを合わせる
    max_len = max(len(lst) for lst in rows_data)
    for i in range(len(rows_data)):
        if len(rows_data[i]) < max_len:
            rows_data[i] += [""] * (max_len - len(rows_data[i]))

    # 列名は自動で Col1, Col2... に
    df = pd.DataFrame({f"Col{idx+1}": rows_data[idx] for idx in range(len(rows_data))})

    st.subheader("解析データ（手書き・列自動検出）")
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
