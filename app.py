import streamlit as st
import cv2
import pytesseract
import pandas as pd
import tempfile
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.title("⚾ 野球スコアOCR登録ツール（試作）")

# Google Sheets 認証
def connect_gsheet():
    # Streamlit Cloud の Secrets に credentials を保存して呼び出し
    # st.secrets["gcp_service_account"] に JSON を入れておく
    creds_dict = st.secrets["gcp_service_account"]
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

uploaded_file = st.file_uploader("スコアシート画像をアップロードしてください", type=["jpg","jpeg","png"])

if uploaded_file:
    # 一時ファイルに保存
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(uploaded_file.read())
        img_path = tmp.name

    # OCR
    img = cv2.imread(img_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    text = pytesseract.image_to_string(gray, lang="jpn")

    st.subheader("OCR抽出結果（生データ）")
    st.text(text)

    # 簡易パース（例：行ごとに「打順 選手名 結果」）
    rows = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            rows.append(parts[:3])  # [打順, 選手名, 結果]

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
                st.error(f"Googleスプレッドシート登録でエラー: {e}")
