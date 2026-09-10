# TECH RADAR

Slack に AI・VR/XR・起業関連の注目ニュースを毎朝自動投稿する無料ニュースレーダーです。

## できること

- AI / VR・XR / Startup の3カテゴリを収集
- 公開RSS/Atomフィードを利用（AI API不要）
- タイトル・掲載元・公開時刻・短い説明・元記事URLをSlackへ投稿
- キーワード、情報源の信頼度、新しさを使ってスコアリング
- 同一タイトル・同一URLの記事を重複除去
- 各カテゴリ上位4件を表示
- GitHub Actionsから毎朝8:00（Asia/Tokyo）に自動実行

## 情報源

### AI

- OpenAI
- Anthropic
- Microsoft AI
- Hugging Face
- TechCrunch AI

### VR / XR

- Road to VR
- UploadVR

### Startup

- TechCrunch Startups
- Hacker News
- Product Hunt

フィードが一時的に取得できなくても、他の情報源の処理は継続します。

## Slack投稿例

```text
☀️ TECH RADAR
2026.09.10

🤖 AI
1. Article title
🔥 MUST READ ・ OpenAI ・ 09/10 08:10
> RSSから取得した短い説明
🔗 元記事を読む
```

## 必要なGitHub Secret

Repository の `Settings > Secrets and variables > Actions` に以下を登録します。

```text
SLACK_WEBHOOK_URL
```

Webhook URLはコードやREADMEに直接書かないでください。

## 手動テスト

GitHub の `Actions > Daily Tech Radar > Run workflow` から実行できます。

## 自動テスト

```bash
python -m unittest -v
```

ニュース選別ロジック、要約整形、重複除去などをテストします。
