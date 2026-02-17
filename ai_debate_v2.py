"""
AI Debate v2 - AI同士のディベートを観戦するアプリ（進化版）
新機能:
- ジャッジAI: 討論終了後に勝敗を判定
- アニメキャラ表示: リアルタイムで口パク付きキャラクターを表示
"""

import time
import sys
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from character_window import CharacterWindow


class RateLimitError(Exception):
    """API制限エラー"""
    pass


# バックエンドの選択（ollama または gemini）
BACKEND = "groq"  # "ollama", "gemini", or "groq"

# Ollama設定
OLLAMA_MODEL = "llama3.2"

# Gemini設定（無料枠: 15リクエスト/分）
GEMINI_API_KEY = "AIzaSyB7WOCczBjpmBt0dtt44zu_dFDMruUfpuI"

# Groq設定（無料枠: 30リクエスト/分、14400リクエスト/日）
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")  # 環境変数から取得


def get_llm_response(prompt: str, system_prompt: str, max_tokens: int = 200) -> str:
    """LLMからレスポンスを取得"""
    if BACKEND == "ollama":
        return get_ollama_response(prompt, system_prompt)
    elif BACKEND == "gemini":
        return get_gemini_response(prompt, system_prompt)
    elif BACKEND == "groq":
        return get_groq_response(prompt, system_prompt, max_tokens)
    else:
        raise ValueError(f"Unknown backend: {BACKEND}")


def get_ollama_response(prompt: str, system_prompt: str) -> str:
    """Ollamaを使用してレスポンスを取得"""
    import requests

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
        },
    )
    response.raise_for_status()
    return response.json()["response"]


def get_gemini_response(prompt: str, system_prompt: str) -> str:
    """Gemini APIを使用してレスポンスを取得"""
    from google import genai
    import os

    api_key = GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY を設定してください")

    client = genai.Client(api_key=api_key)
    full_prompt = f"{system_prompt}\n\n{prompt}"

    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemma-3-12b-it",
                contents=full_prompt
            )
            return response.text
        except Exception as e:
            error_msg = str(e).lower()
            if "quota" in error_msg or "rate" in error_msg or "resource" in error_msg or "exhausted" in error_msg or "429" in error_msg:
                wait_time = 10 * (attempt + 1)
                if attempt < max_retries - 1:
                    print_colored(f" [レート制限、{wait_time}秒待機中...]", "yellow", end="")
                    time.sleep(wait_time)
                    continue
                else:
                    raise RateLimitError("API制限に達しました。しばらく待ってから再試行してください。")
            raise


def get_groq_response(prompt: str, system_prompt: str, max_tokens: int = 200) -> str:
    """Groq APIを使用してレスポンスを取得（超高速）"""
    from groq import Groq
    import os

    api_key = GROQ_API_KEY or os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY を設定してください")

    client = Groq(api_key=api_key)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            error_msg = str(e).lower()
            if "rate" in error_msg or "limit" in error_msg or "429" in error_msg:
                wait_time = 5 * (attempt + 1)
                if attempt < max_retries - 1:
                    print_colored(f" [レート制限、{wait_time}秒待機中...]", "yellow", end="")
                    time.sleep(wait_time)
                    continue
                else:
                    raise RateLimitError("API制限に達しました。しばらく待ってから再試行してください。")
            raise


def create_debater_prompt(role: str, topic: str, personality: dict) -> str:
    """ディベーターのシステムプロンプトを作成"""
    stance = "賛成" if role == "pro" else "反対"

    return f"""あなたは{personality['name']}という名前の{personality['age']}の{personality['job']}です。
「{topic}」に{stance}の立場で議論しています。

【最重要ルール】
- 必ず「{topic}」の具体的な内容について話すこと
- 具体例や根拠を挙げて議論すること
- 相手の人格ではなく、相手の「主張の内容」に反論すること

【話し方のルール】
- 一文〜二文で返答する
- {personality['tone']}で話す
- 「〜です」「〜ます」の説明口調は禁止

【禁止事項】
- 相手を「化石」「頭が固い」など人格攻撃すること
- 抽象的な言い合いに終始すること
- テーマから脱線すること

性格: {personality['personality']}"""


def create_judge_prompt(topic: str, history: list, pro_name: str, con_name: str) -> str:
    """ジャッジ用のプロンプト作成"""
    conversation = ""
    for i, msg in enumerate(history):
        speaker = pro_name if i % 2 == 0 else con_name
        conversation += f"{speaker}: {msg}\n"

    return f"""あなたは公平なディベートの審判です。
以下の議論を評価し、勝者を決定してください。

【議題】
{topic}

【議論内容】
{conversation}

【評価基準】
1. 論理性（主張に一貫性があるか）
2. 具体例の質（説得力のある例を挙げているか）
3. 反論力（相手の主張に効果的に反論しているか）
4. 説得力（聞き手を納得させられるか）

【回答形式】
以下の形式で回答してください：

🏆 勝者: [勝者の名前]

📊 評価:
- {pro_name}（賛成派）: [点数]/100点
  [評価コメント]
- {con_name}（反対派）: [点数]/100点
  [評価コメント]

💬 総評:
[全体的な講評を2-3文で]"""


def judge_debate(topic: str, history: list, pro_name: str, con_name: str) -> str:
    """討論を評価して勝者を決定"""
    judge_system = """あなたは公平で客観的なディベートの審判です。
両者の議論を冷静に分析し、論理性と説得力に基づいて判定します。
感情的にならず、具体的な根拠を持って評価してください。"""

    judge_prompt = create_judge_prompt(topic, history, pro_name, con_name)

    print_colored("\n⚖️  ジャッジAIが討論を評価中...\n", "cyan")

    result = get_llm_response(judge_prompt, judge_system, max_tokens=500)
    return result


# 音声設定
VOICE_ENABLED = True

# キャラクターウィンドウ設定
CHARACTER_WINDOW_ENABLED = False  # Trueにするとキャラ表示（実験的）

# キャラクター設定
CHARACTERS = {
    "pro": {
        "name": "タケシ",
        "age": "28歳",
        "job": "IT企業勤務",
        "tone": "カジュアルなタメ口",
        "personality": "熱くなりやすい、負けず嫌い、たまに皮肉を言う",
        "voice": "Rocko (日本語（日本）)",
    },
    "con": {
        "name": "ユミ",
        "age": "32歳",
        "job": "出版社編集者",
        "tone": "少し辛辣だけど知的な口調",
        "personality": "冷静、論理的、相手の矛盾を突くのが得意",
        "voice": "Kyoko",
    }
}


def print_colored(text: str, color: str, end: str = "\n"):
    """色付きテキストを出力"""
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "reset": "\033[0m",
    }
    print(f"{colors.get(color, '')}{text}{colors['reset']}", end=end)


def print_header():
    """ヘッダーを表示"""
    print("\n" + "=" * 60)
    print_colored("   AI DEBATE v2 - AI同士のディベートを観戦しよう", "cyan")
    print_colored("   ✨ 新機能: キャラクター表示 & ジャッジAI", "yellow")
    print("=" * 60 + "\n")


def speak_simple(text: str, voice: str):
    """シンプルな音声読み上げ（ブロッキング）"""
    import subprocess
    subprocess.run(["say", "-v", voice, "-r", "140", text], check=True)


def run_debate():
    """ディベートを実行"""
    print_header()

    pro_name = CHARACTERS["pro"]["name"]
    con_name = CHARACTERS["con"]["name"]

    # キャラクターウィンドウ（オプション）
    char_window = None
    if CHARACTER_WINDOW_ENABLED:
        char_window = CharacterWindow(pro_name, con_name)
        char_window.start()

    # 議題を入力
    print_colored("議題を入力してください（例: AIは人間の仕事を奪う）", "yellow")
    topic = input("> ").strip()
    if not topic:
        topic = "AIは人間の仕事を奪う"

    print(f"\n議題: 「{topic}」\n")
    print_colored("賛成派 🟢 vs 反対派 🔴", "magenta")
    print("-" * 60)
    print("Ctrl+C で終了（終了後にジャッジAIが判定します）\n")

    # プロンプト作成
    pro_system = create_debater_prompt("pro", topic, CHARACTERS["pro"])
    con_system = create_debater_prompt("con", topic, CHARACTERS["con"])

    print(f"\n{pro_name}（賛成派）vs {con_name}（反対派）\n")

    # 会話履歴
    history = []

    # 最初の発言
    initial_prompt = f"「{topic}」について、具体例を一つ挙げて自分の意見を言って。"

    turn = 0
    api_calls = 0

    try:
        while True:
            turn += 1

            # === 賛成派の発言 ===
            print_colored(f"{pro_name}: ", "green", end="")
            sys.stdout.flush()

            if turn == 1:
                pro_prompt = initial_prompt
            else:
                pro_prompt = f"{con_name}「{history[-1]}」\n\n↑この主張に対して具体例や根拠を挙げて反論して。"

            pro_response = get_llm_response(pro_prompt, pro_system)
            api_calls += 1
            pro_text = pro_response.strip()
            print(pro_text)
            history.append(pro_text)

            # 音声読み上げ
            if VOICE_ENABLED:
                if char_window:
                    char_window.speak_with_animation(pro_text, "pro", CHARACTERS["pro"]["voice"])
                else:
                    speak_simple(pro_text, CHARACTERS["pro"]["voice"])

            # レート制限対策
            time.sleep(3)

            # === 反対派の発言 ===
            print_colored(f"{con_name}: ", "red", end="")
            sys.stdout.flush()

            con_prompt = f"{pro_name}「{pro_text}」\n\n↑この主張に対して具体例や根拠を挙げて反論して。"
            con_response = get_llm_response(con_prompt, con_system)
            api_calls += 1
            con_text = con_response.strip()
            print(con_text)
            history.append(con_text)

            # 音声読み上げ
            if VOICE_ENABLED:
                if char_window:
                    char_window.speak_with_animation(con_text, "con", CHARACTERS["con"]["voice"])
                else:
                    speak_simple(con_text, CHARACTERS["con"]["voice"])

            # レート制限対策
            time.sleep(3)

    except KeyboardInterrupt:
        print("")
    except RateLimitError as e:
        print_colored(f"\n\n⚠️ {e}", "yellow")
        print_colored("1分待つか、明日(日本時間9時リセット)に再開してください。", "yellow")

    # ディベート終了
    print("\n" + "=" * 60)
    print_colored("ディベート終了！", "cyan")
    print(f"ラウンド数: {turn}  API使用: {api_calls}回")
    print("=" * 60)

    # ジャッジAIによる判定
    if len(history) >= 2:
        try:
            judge_result = judge_debate(topic, history, pro_name, con_name)
            print_colored("\n" + "=" * 60, "yellow")
            print_colored("   ⚖️  ジャッジAI判定結果", "yellow")
            print_colored("=" * 60 + "\n", "yellow")
            print(judge_result)
            print()
        except Exception as e:
            print_colored(f"\n⚠️ ジャッジAIでエラーが発生しました: {e}", "red")
    else:
        print_colored("\n（議論が短すぎるため、判定をスキップします）", "yellow")

    # キャラクターウィンドウを閉じる
    if char_window:
        char_window.close()


if __name__ == "__main__":
    run_debate()
