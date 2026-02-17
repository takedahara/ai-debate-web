# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

AI同士のディベート・グループディスカッションをシミュレートするPythonアプリ群。複数のLLMバックエンド（Groq, Gemini, Ollama）と音声合成（macOS say, VOICEVOX, Web Speech API）を組み合わせ、Tkinter GUIまたはWebブラウザでリアルタイム表示する。

## 実行方法

### Webアプリ版（推奨）

```bash
# 依存関係のインストール
pip install -r requirements.txt

# 環境変数設定
cp .env.example .env
# .env に GROQ_API_KEY を設定

# サーバー起動
uvicorn api_server.main:app --reload --port 8000

# ブラウザで http://localhost:8000 を開く
```

### デスクトップ版（Tkinter）

```bash
# 基本版（CUI、macOS sayで音声）
python ai_debate.py

# GUI版（Tkinter）
python ai_debate_gui.py

# VOICEVOX版（要VOICEVOXローカル起動）
python ai_debate_voicevox.py

# YouTube配信向け版（表情・エフェクト付き）
python ai_debate_youtube.py

# GDシミュレーター（5人グループディスカッション、要VOICEVOX）
python ai_gd_simulator.py
```

## アーキテクチャ

### Webアプリ構成

```
AI_chat2/
├── api_server/          # FastAPI サーバー
│   ├── main.py          # エントリポイント、静的ファイル配信
│   ├── routes/
│   │   ├── health.py    # GET /health
│   │   └── debate.py    # POST /debate/{start,turn,judge}
│   └── middleware/
│       ├── cors.py      # CORS設定
│       ├── rate_limit.py # IPベースレート制限
│       └── logging.py   # JSONログ
├── debate_core/         # コアロジック（UIから独立）
│   ├── types.py         # Character, DebateSession, TurnResult等
│   ├── config.py        # デフォルトキャラ設定、LLM設定
│   ├── prompts.py       # プロンプト生成関数
│   └── session.py       # SessionManager（セッション管理）
├── llm_client/          # LLM抽象化
│   ├── exceptions.py    # RateLimitError, APIKeyError
│   └── groq_client.py   # Groq API実装
└── web/                 # フロントエンド
    ├── index.html
    ├── css/style.css
    └── js/
        ├── api.js       # APIクライアント
        ├── speech.js    # Web Speech API ラッパー
        └── app.js       # メインアプリケーション
```

### LLMバックエンド
- **Groq** (デフォルト): `llama-3.3-70b-versatile`を使用、最も高速
- **Gemini**: `gemma-3-12b-it`を使用
- **Ollama**: ローカルLLM、`llama3.2`など

### 音声合成
- **Web Speech API**: ブラウザネイティブ（Webアプリ版）
- **macOS say**: `Kyoko`(女性)、`Rocko (日本語（日本）)`(男性)
- **VOICEVOX**: `http://localhost:50021`で起動が必要、speaker_idでキャラ指定

### GUI構成（デスクトップ版）
全GUIアプリは以下の共通パターンを使用：
- メインスレッド: Tkinter UIループ
- バックグラウンドスレッド: LLM API呼び出し + 音声生成
- `queue.Queue`: スレッド間通信（`action`フィールドでUI更新を指示）
- 先読み最適化: `ThreadPoolExecutor`で次の発言のテキスト・音声を事前生成

### ファイル構成
| ファイル | 説明 |
|---------|------|
| `api_server/` | FastAPI Webサーバー |
| `debate_core/` | コアロジック（共有モジュール） |
| `llm_client/` | LLMクライアント抽象化 |
| `web/` | Webフロントエンド |
| `ai_debate.py` | CUI版、基本構造 |
| `ai_debate_v2.py` | GUI + ジャッジAI機能 |
| `ai_debate_gui.py` | GUI版、キャラ画像自動生成 |
| `ai_debate_voicevox.py` | VOICEVOX音声版 |
| `ai_debate_youtube.py` | 表情変化・字幕・パーティクル演出 |
| `ai_gd_simulator.py` | 5人GDシミュレーター |
| `character_window.py` | キャラ表示ウィンドウモジュール |

## 環境変数

APIキーは環境変数で設定（`.env`ファイル対応）：
- `GROQ_API_KEY` (必須)
- `GEMINI_API_KEY`
- `ALLOWED_ORIGINS` - CORS許可オリジン（カンマ区切り）
- `RATE_LIMIT_PER_MINUTE` - 分あたりリクエスト制限

## API仕様

### GET /health
```json
{"status": "healthy", "timestamp": "...", "version": "1.0.0"}
```

### POST /debate/start
```json
// Request
{"topic": "AIは人間の仕事を奪う"}
// Response
{"session_id": "uuid", "topic": "...", "pro": {...}, "con": {...}}
```

### POST /debate/turn
```json
// Request
{"session_id": "uuid"}
// Response
{"turn_number": 1, "speaker": {...}, "text": "...", "next_speaker": "con"}
```

### POST /debate/judge
```json
// Request
{"session_id": "uuid"}
// Response
{"verdict": {...}, "history": [...], "turn_count": 6}
```

## 注意事項

- WebアプリはGroq APIキーが必須（環境変数で設定）
- VOICEVOX版は事前にVOICEVOXアプリを起動しておく必要あり
- macOS固有コマンド（`say`, `afplay`）を使用しているため、他OSでは音声部分の修正が必要
- アセット画像（`assets/`, `assets_gd/`, `assets_youtube/`）は初回起動時にPillowで自動生成

## デプロイ

Renderへのデプロイは`render.yaml`を参照。環境変数`GROQ_API_KEY`の設定が必要。
