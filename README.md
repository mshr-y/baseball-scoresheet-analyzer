# baseball-scoresheet-analyzer
野球スコアシートアナライザー

## 使い方
1. GitHub にこのリポジトリを置く
2. Streamlit Cloud に接続してデプロイ
3. `credentials.json` の内容を Streamlit Cloud の Secrets に登録
   - `[左メニュー] -> [App settings] -> [Secrets]`
   - キー名は `gcp_service_account`
   - [gcp_service_account]
   - type = "service_account"
   - project_id = "xxxx"
   - private_key_id = "xxxx"
   - private_key = "-----BEGIN PRIVATE KEY-----\n....\n-----END PRIVATE KEY-----\n"  
   - client_email = "xxxxx@xxxxx.iam.gserviceaccount.com"
   ...

4. アプリを開いてスコアシート画像をアップロード
5. OCR解析 → Googleスプレッドシートに書き込み

