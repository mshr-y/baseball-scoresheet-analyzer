import streamlit as st
import cv2
import pytesseract
import pandas as pd
import tempfile
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.title("⚾ 野球スコアOCR登録ツール（精度改善版）")

# -----------------------------
# Google Sheets 認証関数
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
    # 一時ファイルに保存
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(uploaded_file.read())
        img_path = tmp.name

    # 画像読み込み
    img = cv2.imread(img_path)

    # -----------------------------
    # 画像前処理
    # -----------------------------
    # グレースケール化
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # ノイズ除去
    gray = cv2.medianBlur(gray, 3)

    # コントラスト強化
    gray = cv2.equalizeHist(gray)

    # 二値化
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # サイズ拡大（小さい文字向け）
    scale_percent = 150  # 1.5倍
    width = int(thresh.shape[1] * scale_percent / 100)
    height = int(thresh.shape[0] * scale_percent / 100)
    dim = (width, height)
    resized = cv2.resize(thresh, dim, interpolation=cv2.INTER_LINEAR)

    # Streamlit に前処理後の画像を表示
    st.subheader("前処理後の画像")
    st.image(resized, use_column_width=True)

    # -----------------------------
    # OCR
    # -----------------------------
    custom_config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(resized, lang="jpn", config=custom_config)

    st.subheader("OCR抽出結果（生データ）")
    st.text(text)

    # -----------------------------
    # 簡易パース（例：打順 選手名 結果）
    # -----------------------------
    rows = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            rows.append(parts[:3])  # [打順, 選手名, 結果]

    if rows:
        df = pd.DataFrame(rows, columns=["打順", "選手名", "結果"])
        st.subheader("解析データ（仮）")
        st.dataframe(df)

        # -----------------------------
        # Googleスプレッドシートに登録
        # -----------------------------
        if st.button("Googleスプレッドシートに登録"):
            try:
                client = connect_gsheet()
                sheet = client.open("野球スコア").sheet1
                for row in rows:
                    sheet.append_row(row)
                st.success("✅ Googleスプレッドシートに登録しました！")
            except Exception as e:
                st.error(f"Googleスプレッドシート登録でエラー: {e}")
