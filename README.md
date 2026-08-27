# 世界経済5分チェック WEB第4版

GitHub + Streamlit Community Cloudでブラウザ公開できます。

## 機能
- 日経平均 / S&P500 / NASDAQ / ドル円 / 米10年債 / WTI / 金
- Trading Economics APIの予想・実績・前回値
- サプライズ自動計算
- 今日の最重要材料TOP3
- Google News RSS
- OpenAI APIによる因果分析
- Streamlit SecretsでAPIキーを管理

## 公開手順
1. GitHubで新規リポジトリを作る
2. `streamlit_app.py` と `requirements.txt` をアップロード
3. Streamlit Community CloudでGitHubに接続
4. Create appでリポジトリと `streamlit_app.py` を選んでDeploy
5. Advanced settings / Secrets に以下を登録:
TRADINGECONOMICS_API_KEY = "あなたのキー"
OPENAI_API_KEY = "あなたのキー"
OPENAI_MODEL = "gpt-5"

## 注意
市場予想はAPI利用を前提とします。APIの料金・利用規約・再配布条件を確認してください。
