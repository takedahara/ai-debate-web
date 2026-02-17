"""
AI Debate - AI同士のディベートを観戦するアプリ
2つのAIが賛成派と反対派に分かれて議論を続けます
"""

import time
import sys
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, Future


class RateLimitError(Exception):
    """API制限エラー"""
    pass


# バックエンドの選択（ollama または gemini）
BACKEND = "groq"  # "ollama", "gemini", or "groq"

# Ollama設定
OLLAMA_MODEL = "llama3.2"  # または gemma2, mistral など

# Gemini設定（無料枠: 15リクエスト/分）
GEMINI_API_KEY = "AIzaSyB7WOCczBjpmBt0dtt44zu_dFDMruUfpuI"

# Groq設定（無料枠: 30リクエスト/分、14400リクエスト/日）
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")  # 環境変数から取得


def get_llm_response(prompt: str, system_prompt: str) -> str:
    """LLMからレスポンスを取得"""
    if BACKEND == "ollama":
        return get_ollama_response(prompt, system_prompt)
    elif BACKEND == "gemini":
        return get_gemini_response(prompt, system_prompt)
    elif BACKEND == "groq":
        return get_groq_response(prompt, system_prompt)
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
    """Gemini APIを使用してレスポンスを取得（新しいgoogle-genaiパッケージ）"""
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
                # レート制限の場合は待ってリトライ
                wait_time = 10 * (attempt + 1)  # 10秒、20秒、30秒...
                if attempt < max_retries - 1:
                    print_colored(f" [レート制限、{wait_time}秒待機中...]", "yellow", end="")
                    time.sleep(wait_time)
                    continue
                else:
                    raise RateLimitError("API制限に達しました。しばらく待ってから再試行してください。")
            raise


def get_groq_response(prompt: str, system_prompt: str) -> str:
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
                max_tokens=200,
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


# 音声設定
VOICE_ENABLED = True  # 音声をオフにしたい場合は False

# キャラクター設定
CHARACTERS = {
    "pro": {
        "name": "タケシ",
        "age": "28歳",
        "job": "IT企業勤務",
        "tone": "カジュアルなタメ口",
        "personality": "熱くなりやすい、負けず嫌い、たまに皮肉を言う",
        "voice": "Rocko (日本語（日本）)",  # 男性声
    },
    "con": {
        "name": "ユミ",
        "age": "32歳",
        "job": "出版社編集者",
        "tone": "少し辛辣だけど知的な口調",
        "personality": "冷静、論理的、相手の矛盾を突くのが得意",
        "voice": "Kyoko",  # 女性声
    }
}


def speak(text: str, voice: str):
    """テキストを音声で読み上げる（ブロッキング）"""
    if not VOICE_ENABLED:
        return
    subprocess.run(["say", "-v", voice, "-r", "140", text], check=True)


def speak_async(text: str, voice: str) -> threading.Thread:
    """テキストを音声で読み上げる（非同期）"""
    if not VOICE_ENABLED:
        return None
    thread = threading.Thread(target=speak, args=(text, voice))
    thread.start()
    return thread


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
    print_colored("   AI DEBATE - AI同士のディベートを観戦しよう", "cyan")
    print("=" * 60 + "\n")


def run_debate():
    """ディベートを実行"""
    print_header()

    # 議題を入力
    print_colored("議題を入力してください（例: AIは人間の仕事を奪う）", "yellow")
    topic = input("> ").strip()
    if not topic:
        topic = "AIは人間の仕事を奪う"

    print(f"\n議題: 「{topic}」\n")
    print_colored("賛成派 🟢 vs 反対派 🔴", "magenta")
    print("-" * 60)
    print("Ctrl+C で終了\n")

    # プロンプト作成
    pro_system = create_debater_prompt("pro", topic, CHARACTERS["pro"])
    con_system = create_debater_prompt("con", topic, CHARACTERS["con"])

    print(f"\n{CHARACTERS['pro']['name']}（賛成派）vs {CHARACTERS['con']['name']}（反対派）\n")

    # 会話履歴
    history = []

    # 最初の発言
    initial_prompt = f"「{topic}」について、具体例を一つ挙げて自分の意見を言って。"

    turn = 0
    api_calls = 0
    max_calls_warning = 1400  # 1500回/日の制限に近づいたら警告

    pro_name = CHARACTERS["pro"]["name"]
    con_name = CHARACTERS["con"]["name"]

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
            speak(pro_text, CHARACTERS["pro"]["voice"])

            # レート制限対策：次のリクエストまで待機
            time.sleep(5)

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
            speak(con_text, CHARACTERS["con"]["voice"])

            # レート制限対策：次のリクエストまで待機
            time.sleep(5)

    except KeyboardInterrupt:
        print("")  # 改行
    except RateLimitError as e:
        print_colored(f"\n\n⚠️ {e}", "yellow")
        print_colored("1分待つか、明日(日本時間9時リセット)に再開してください。", "yellow")

    print("\n" + "=" * 60)
    print_colored("ディベート終了！", "cyan")
    print(f"ラウンド数: {turn}  API使用: {api_calls}回")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_debate()
