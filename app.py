import streamlit as st
import cv2
import pandas as pd
import numpy as np
import tempfile
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import easyocr
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

    # リサイズ（幅1000px以下）
    h, w = gray.shape
    if w > 1000:
        ratio = 1000 / w
        gray = cv2.resize(gray, (1000, int(h*ratio)), interpolation=cv2.INTER_AREA)
        img = cv2.resize(img, (1000, int(h*ratio)), interpolation=cv2.INTER_AREA)

    # ノイズ除去・コントラスト強化
    gray = cv2.medianBlur(gray, 3)
    gray = cv2.equalizeHist(gray)

    # 二値化反転
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # OCR 実行
    result = reader.readtext(gray, detail=0)
    text_lines = [line.strip() for line in result if line.strip()]

    st.subheader("OCR抽出結果（生データ）")
    st.text("\n".join(text_lines))

    # 簡易パース例：行ごとに分割
    rows = []
    for line in text_lines:
        parts = line.split()
        if len(parts) >= 3:
            rows.append(parts[:3])

    if rows:
        df = pd.DataFrame(rows, columns=["打順", "選手名", "結果"])
        st.subheader("解析データ（仮）")
        st.dataframe(df)

        if st.button("Googleスプレッドシートに登録"):
            try:
                client = connect_gsheet()
                sheet = client.open("野球スコア").sheet1
                for row in rows:
                    sheet.append_row(row)
                st.success("✅ Googleスプレッドシートに登録しました！")
            except Exception as e:
                st.error(f"登録エラー: {e}")

    # メモリ解放
    del img, gray, thresh
    gc.collect()
