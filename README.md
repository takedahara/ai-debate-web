# AI Debate - AIディベートシミュレーター

AIキャラクター同士がディベートを行うWebアプリケーション。Groq APIを使用してLLMでテキスト生成し、ブラウザのWeb Speech APIで音声読み上げを行います。

## デモ

![AI Debate Screenshot](docs/screenshot.png)

## 機能

- AIキャラクター2人による自動ディベート
- リアルタイムな発言生成（Groq API / LLaMA 3.3）
- ブラウザでの音声読み上げ（Web Speech API）
- ジャッジによる勝敗判定
- レスポンシブデザイン
- **ユーザー自身のAPIキーを使用**（ブラウザに保存）

## クイックスタート

### 1. 依存関係のインストール

```bash
cd AI_chat2
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. サーバー起動

```bash
uvicorn api_server.main:app --reload --port 8000
```

### 3. ブラウザでアクセス

http://localhost:8000 を開く

## 使い方

1. [Groq Console](https://console.groq.com/keys) で無料のAPIキーを取得
2. サイトにアクセスし、APIキーを入力（ブラウザに保存されます）
3. 議題を入力して「ディベート開始」
4. 「次のターン」で会話を進める
5. 「終了＆判定」で勝敗を決定

**Note:** APIキーはブラウザのlocalStorageに保存され、サーバーには保存されません。

## API仕様

### GET /health
ヘルスチェック

```bash
curl http://localhost:8000/health
```

### POST /debate/start
ディベートセッション開始

```bash
curl -X POST http://localhost:8000/debate/start \
  -H "Content-Type: application/json" \
  -d '{"topic": "AIは人間の仕事を奪う"}'
```

### POST /debate/turn
ディベートターン実行

```bash
curl -X POST http://localhost:8000/debate/turn \
  -H "Content-Type: application/json" \
  -d '{"session_id": "your-session-id"}'
```

### POST /debate/judge
ジャッジ判定

```bash
curl -X POST http://localhost:8000/debate/judge \
  -H "Content-Type: application/json" \
  -d '{"session_id": "your-session-id"}'
```

## プロジェクト構成

```
AI_chat2/
├── api_server/          # FastAPI サーバー
│   ├── main.py          # エントリポイント
│   ├── routes/          # APIルート
│   └── middleware/      # CORS, レート制限, ログ
├── debate_core/         # コアロジック
│   ├── types.py         # データクラス
│   ├── config.py        # 設定
│   ├── prompts.py       # プロンプト生成
│   └── session.py       # セッション管理
├── llm_client/          # LLMクライアント
│   └── groq_client.py   # Groq API実装
├── web/                 # フロントエンド
│   ├── index.html
│   ├── css/style.css
│   └── js/              # JavaScript
└── (既存のTkinterアプリ)
```

## デプロイ

### Renderへのデプロイ

1. GitHubにリポジトリをプッシュ
2. [Render](https://render.com) でNew Web Serviceを作成
3. リポジトリを接続
4. デプロイ（ユーザーは各自のAPIキーを使用するため、環境変数設定は不要）

詳細は `render.yaml` を参照。

## 既存アプリ（デスクトップ版）

VOICEVOX版などのTkinterアプリも引き続き利用可能です：

```bash
# VOICEVOX版（要VOICEVOXローカル起動）
python ai_debate_voicevox.py

# GUI版
python ai_debate_gui.py

# YouTube配信向け版
python ai_debate_youtube.py
```

## 環境変数

| 変数名 | 必須 | 説明 |
|--------|------|------|
| `GROQ_API_KEY` | No | サーバーデフォルトのAPIキー（ユーザーが入力しない場合に使用） |
| `ALLOWED_ORIGINS` | No | CORS許可オリジン（カンマ区切り） |
| `RATE_LIMIT_PER_MINUTE` | No | 分あたりリクエスト制限（デフォルト: 30） |
| `PORT` | No | サーバーポート（デフォルト: 8000） |

## 技術スタック

- **バックエンド**: FastAPI, Python 3.9+
- **LLM**: Groq API (LLaMA 3.3 70B)
- **フロントエンド**: Vanilla JS, Web Speech API
- **音声**: Web Speech API（サーバーサイド音声生成なし）

## ライセンス

MIT License
