# TECH RADAR

Slack に AI・VR/XR・起業関連の注目ニュースを毎朝自動投稿する無料ニュースレーダーです。

## できること

- AI / VR・XR / Startup の3カテゴリを収集
- 公開RSS/Atomフィードを利用
- キーワード、情報源の信頼度、新しさを使ってスコアリング
- 同一タイトル・同一URLの記事を重複除去
- まず媒体ごとに1記事ずつ選び、同じサイトへの偏りを抑える
- 各カテゴリ上位4件を表示
- Slackの親投稿は1日1件にまとめ、詳細はスレッドへ投稿
- 英語タイトルとRSSの短い説明を日本語へ自動翻訳
- 原文タイトル・掲載元・公開時刻・元記事URLも残す
- GitHub Actionsから毎朝8:00（Asia/Tokyo）に自動実行

## Slack投稿イメージ

チャンネル本体にはコンパクトな親投稿だけを出します。

```text
☀️ TECH RADAR
2026.09.10

今日の AI・VR/XR・Startup ニュースをピックアップしました。

🤖 AI  4件
🥽 VR / XR  3件
🚀 STARTUP  4件

📡 本日のニュース: 11件
👇 和訳・原文・元記事URLはこの投稿のスレッドへ
```

スレッドにはカテゴリごとの詳細を投稿します。

```text
🤖 AI

1. OpenAIが新しいエージェントを発表
Original: OpenAI launches a new agent
> 🇯🇵 開発者向けの新しい自動化機能を紹介しています。
🔥 MUST READ ・ OpenAI ・ 09/10 08:10
🔗 元記事を読む
```

## 和訳について

和訳にはオープンソースの `Argos Translate` をGitHub Actions内で使用します。
外部の有料AI APIは使いません。

初回実行時に英語 → 日本語の翻訳モデルを取得し、GitHub Actionsのキャッシュに保存します。
翻訳が一時的に使えない場合は処理全体を止めず、英語原文を残します。

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

## Slack Appの設定

スレッド投稿には Incoming Webhook だけでなく Slack Bot Token を使用します。

Slack App の `OAuth & Permissions` で Bot Token Scope に以下を追加してください。

```text
chat:write
```

その後、アプリをWorkspaceへ再インストールし、投稿先チャンネルにBotを追加します。

## 必要なGitHub Secrets

Repository の `Settings > Secrets and variables > Actions` に以下を登録します。

```text
SLACK_BOT_TOKEN
SLACK_CHANNEL_ID
```

- `SLACK_BOT_TOKEN`: Slack App の Bot User OAuth Token（`xoxb-...`）
- `SLACK_CHANNEL_ID`: 投稿先チャンネルのID（`C...`）

既存の `SLACK_WEBHOOK_URL` はフォールバック用として残せます。
Bot Token / Channel ID が未設定の場合は、従来どおりWebhookによる1投稿形式で動作します。

トークンやWebhook URLはコードやREADMEへ直接書かないでください。

## 手動テスト

GitHub の `Actions > Daily Tech Radar > Run workflow` から実行できます。

Bot Token と Channel ID を設定した後に手動実行すると、親投稿とスレッド返信の動作を確認できます。

## 自動テスト

```bash
python -m unittest -v
```

ニュース選別ロジック、要約整形、重複除去、Slackスレッド用メッセージ、翻訳失敗時のフォールバックなどをテストします。
