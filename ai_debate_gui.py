"""
AI Debate GUI版 - キャラクターウィンドウ付き
TkinterをメインスレッドでAI処理をバックグラウンドで実行
"""

import tkinter as tk
from tkinter import Canvas, simpledialog
from PIL import Image, ImageDraw, ImageTk
import os
import threading
import subprocess
import tempfile
import time
import queue


class RateLimitError(Exception):
    """API制限エラー"""
    pass


# バックエンド設定
BACKEND = "groq"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")  # 環境変数から取得

# キャラクター設定
CHARACTERS = {
    "pro": {
        "name": "タケシ",
        "age": "28歳",
        "job": "IT企業勤務",
        "tone": "カジュアルなタメ口",
        "personality": "熱くなりやすい、負けず嫌い、たまに皮肉を言う",
        "voice": "Rocko (日本語（日本）)",
        "color": "green",
    },
    "con": {
        "name": "ユミ",
        "age": "32歳",
        "job": "出版社編集者",
        "tone": "少し辛辣だけど知的な口調",
        "personality": "冷静、論理的、相手の矛盾を突くのが得意",
        "voice": "Kyoko",
        "color": "red",
    }
}


def get_groq_response(prompt: str, system_prompt: str, max_tokens: int = 200) -> str:
    """Groq APIを使用してレスポンスを取得"""
    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY)

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
                    time.sleep(wait_time)
                    continue
                else:
                    raise RateLimitError("API制限")
            raise


def create_debater_prompt(role: str, topic: str, personality: dict) -> str:
    """ディベーターのシステムプロンプトを作成"""
    stance = "賛成" if role == "pro" else "反対"
    return f"""あなたは{personality['name']}という名前の{personality['age']}の{personality['job']}です。
「{topic}」に{stance}の立場で議論しています。

【最重要ルール】
- 必ず「{topic}」の具体的な内容について話すこと
- 具体例や根拠を挙げて議論すること

【話し方のルール】
- 一文〜二文で返答する
- {personality['tone']}で話す
- 「〜です」「〜ます」の説明口調は禁止

性格: {personality['personality']}"""


def create_judge_prompt(topic: str, history: list, pro_name: str, con_name: str) -> str:
    """ジャッジ用のプロンプト作成"""
    conversation = ""
    for i, msg in enumerate(history):
        speaker = pro_name if i % 2 == 0 else con_name
        conversation += f"{speaker}: {msg}\n"

    return f"""あなたは公平なディベートの審判です。

【議題】{topic}

【議論内容】
{conversation}

【回答形式】
🏆 勝者: [名前]

📊 評価:
- {pro_name}: [点数]/100点 - [一言評価]
- {con_name}: [点数]/100点 - [一言評価]

💬 総評: [2文で]"""


class DebateApp:
    """AI討論アプリケーション"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AI Debate")
        self.root.geometry("600x500")
        self.root.configure(bg='#2b2b2b')

        self.assets_dir = os.path.join(os.path.dirname(__file__), "assets")
        self._ensure_assets()

        self.images = {}
        self.current_speaker = None
        self.mouth_open = False
        self.is_running = False
        self.history = []
        self.topic = ""

        # メッセージキュー（スレッド間通信）
        self.message_queue = queue.Queue()

        self._setup_ui()
        self._load_images()

        # キューを定期的にチェック
        self.root.after(50, self._process_queue)

    def _ensure_assets(self):
        """画像を準備"""
        if not os.path.exists(self.assets_dir):
            os.makedirs(self.assets_dir)

        for img_name in ["pro_closed.png", "pro_open.png", "con_closed.png", "con_open.png"]:
            img_path = os.path.join(self.assets_dir, img_name)
            if not os.path.exists(img_path):
                self._generate_character_image(img_name)

    def _generate_character_image(self, filename: str):
        """キャラクター画像を生成"""
        size = 200
        img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        is_pro = filename.startswith("pro")
        is_open = "open" in filename

        if is_pro:
            face_color = (135, 206, 250)
            hair_color = (50, 50, 80)
        else:
            face_color = (255, 182, 193)
            hair_color = (139, 69, 19)

        # 髪
        if is_pro:
            draw.ellipse([30, 10, 170, 100], fill=hair_color)
        else:
            draw.ellipse([20, 10, 180, 120], fill=hair_color)
            draw.ellipse([10, 60, 60, 180], fill=hair_color)
            draw.ellipse([140, 60, 190, 180], fill=hair_color)

        # 顔
        draw.ellipse([40, 40, 160, 170], fill=face_color)

        # 目
        eye_y = 90
        draw.ellipse([65, eye_y, 85, eye_y + 25], fill=(255, 255, 255))
        draw.ellipse([115, eye_y, 135, eye_y + 25], fill=(255, 255, 255))
        draw.ellipse([70, eye_y + 5, 82, eye_y + 20], fill=(50, 50, 50))
        draw.ellipse([120, eye_y + 5, 132, eye_y + 20], fill=(50, 50, 50))
        draw.ellipse([72, eye_y + 7, 77, eye_y + 12], fill=(255, 255, 255))
        draw.ellipse([122, eye_y + 7, 127, eye_y + 12], fill=(255, 255, 255))

        # 口
        mouth_y = 135
        if is_open:
            draw.ellipse([85, mouth_y, 115, mouth_y + 20], fill=(200, 100, 100))
        else:
            draw.arc([85, mouth_y, 115, mouth_y + 15], start=0, end=180, fill=(150, 80, 80), width=2)

        img.save(os.path.join(self.assets_dir, filename))

    def _load_images(self):
        """画像をロード"""
        for key in ['pro_closed', 'pro_open', 'con_closed', 'con_open']:
            path = os.path.join(self.assets_dir, f"{key}.png")
            if os.path.exists(path):
                img = Image.open(path).resize((120, 120), Image.Resampling.LANCZOS)
                self.images[key] = ImageTk.PhotoImage(img)

    def _setup_ui(self):
        """UIを構築"""
        # タイトル
        title = tk.Label(self.root, text="AI DEBATE", font=("Helvetica", 20, "bold"),
                        bg='#2b2b2b', fg='white')
        title.pack(pady=10)

        # キャラクターエリア
        char_frame = tk.Frame(self.root, bg='#2b2b2b')
        char_frame.pack(pady=10)

        # 左キャラ（賛成派）
        self.pro_frame = tk.Frame(char_frame, bg='#2b2b2b')
        self.pro_frame.pack(side=tk.LEFT, padx=30)
        self.pro_canvas = Canvas(self.pro_frame, width=130, height=130, bg='#2b2b2b', highlightthickness=0)
        self.pro_canvas.pack()
        tk.Label(self.pro_frame, text=f"🟢 {CHARACTERS['pro']['name']}", font=("Helvetica", 12),
                bg='#2b2b2b', fg='#90EE90').pack()

        # VS
        tk.Label(char_frame, text="VS", font=("Helvetica", 24, "bold"),
                bg='#2b2b2b', fg='yellow').pack(side=tk.LEFT, padx=20)

        # 右キャラ（反対派）
        self.con_frame = tk.Frame(char_frame, bg='#2b2b2b')
        self.con_frame.pack(side=tk.LEFT, padx=30)
        self.con_canvas = Canvas(self.con_frame, width=130, height=130, bg='#2b2b2b', highlightthickness=0)
        self.con_canvas.pack()
        tk.Label(self.con_frame, text=f"🔴 {CHARACTERS['con']['name']}", font=("Helvetica", 12),
                bg='#2b2b2b', fg='#FFB6C1').pack()

        # 議題表示
        self.topic_label = tk.Label(self.root, text="", font=("Helvetica", 14),
                                    bg='#2b2b2b', fg='cyan', wraplength=500)
        self.topic_label.pack(pady=10)

        # 会話ログ
        log_frame = tk.Frame(self.root, bg='#2b2b2b')
        log_frame.pack(pady=10, fill=tk.BOTH, expand=True, padx=20)

        self.log_text = tk.Text(log_frame, height=10, width=60, font=("Helvetica", 11),
                               bg='#1e1e1e', fg='white', wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

        # タグ設定
        self.log_text.tag_configure("pro", foreground="#90EE90")
        self.log_text.tag_configure("con", foreground="#FFB6C1")
        self.log_text.tag_configure("system", foreground="#87CEEB")
        self.log_text.tag_configure("judge", foreground="#FFD700")

        # ボタンエリア
        btn_frame = tk.Frame(self.root, bg='#2b2b2b')
        btn_frame.pack(pady=10)

        self.start_btn = tk.Button(btn_frame, text="開始", font=("Helvetica", 12),
                                   command=self._start_debate, width=10)
        self.start_btn.pack(side=tk.LEFT, padx=10)

        self.stop_btn = tk.Button(btn_frame, text="終了＆判定", font=("Helvetica", 12),
                                  command=self._stop_debate, state=tk.DISABLED, width=10)
        self.stop_btn.pack(side=tk.LEFT, padx=10)

        # 初期描画
        self._draw_characters()

    def _draw_characters(self):
        """キャラクターを描画"""
        self.pro_canvas.delete("all")
        self.con_canvas.delete("all")

        # 賛成派
        pro_key = 'pro_open' if (self.current_speaker == 'pro' and self.mouth_open) else 'pro_closed'
        if pro_key in self.images:
            self.pro_canvas.create_image(65, 65, image=self.images[pro_key])
        if self.current_speaker == 'pro':
            self.pro_canvas.create_oval(2, 2, 128, 128, outline='#00FF00', width=3)

        # 反対派
        con_key = 'con_open' if (self.current_speaker == 'con' and self.mouth_open) else 'con_closed'
        if con_key in self.images:
            self.con_canvas.create_image(65, 65, image=self.images[con_key])
        if self.current_speaker == 'con':
            self.con_canvas.create_oval(2, 2, 128, 128, outline='#FF6B6B', width=3)

    def _process_queue(self):
        """メッセージキューを処理"""
        try:
            while True:
                msg = self.message_queue.get_nowait()
                action = msg.get("action")

                if action == "log":
                    self.log_text.insert(tk.END, msg["text"], msg.get("tag", ""))
                    self.log_text.see(tk.END)
                elif action == "speaker":
                    self.current_speaker = msg["speaker"]
                    self._draw_characters()
                elif action == "mouth":
                    self.mouth_open = msg["open"]
                    self._draw_characters()
                elif action == "done":
                    self.is_running = False
                    self.start_btn.config(state=tk.NORMAL)
                    self.stop_btn.config(state=tk.DISABLED)
                    self.current_speaker = None
                    self._draw_characters()

        except queue.Empty:
            pass

        self.root.after(50, self._process_queue)

    def _start_debate(self):
        """討論開始"""
        topic = simpledialog.askstring("議題", "議題を入力してください:",
                                       initialvalue="AIは人間の仕事を奪う")
        if not topic:
            return

        self.topic = topic
        self.history = []
        self.topic_label.config(text=f"議題: 「{topic}」")
        self.log_text.delete(1.0, tk.END)

        self.is_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        # バックグラウンドで討論開始
        thread = threading.Thread(target=self._debate_loop, daemon=True)
        thread.start()

    def _stop_debate(self):
        """討論終了"""
        self.is_running = False
        self.stop_btn.config(state=tk.DISABLED)

    def _debate_loop(self):
        """討論ループ（バックグラウンド）"""
        pro_name = CHARACTERS["pro"]["name"]
        con_name = CHARACTERS["con"]["name"]

        pro_system = create_debater_prompt("pro", self.topic, CHARACTERS["pro"])
        con_system = create_debater_prompt("con", self.topic, CHARACTERS["con"])

        initial_prompt = f"「{self.topic}」について、具体例を一つ挙げて自分の意見を言って。"

        turn = 0
        while self.is_running:
            turn += 1

            # 賛成派
            if turn == 1:
                pro_prompt = initial_prompt
            else:
                pro_prompt = f"{con_name}「{self.history[-1]}」\n\n↑この主張に反論して。"

            try:
                pro_text = get_groq_response(pro_prompt, pro_system).strip()
            except Exception as e:
                self.message_queue.put({"action": "log", "text": f"\n[エラー: {e}]\n", "tag": "system"})
                break

            self.history.append(pro_text)
            self.message_queue.put({"action": "log", "text": f"{pro_name}: ", "tag": "pro"})
            self.message_queue.put({"action": "log", "text": f"{pro_text}\n\n"})
            self._speak_with_animation(pro_text, "pro", CHARACTERS["pro"]["voice"])

            if not self.is_running:
                break
            time.sleep(2)

            # 反対派
            con_prompt = f"{pro_name}「{pro_text}」\n\n↑この主張に反論して。"
            try:
                con_text = get_groq_response(con_prompt, con_system).strip()
            except Exception as e:
                self.message_queue.put({"action": "log", "text": f"\n[エラー: {e}]\n", "tag": "system"})
                break

            self.history.append(con_text)
            self.message_queue.put({"action": "log", "text": f"{con_name}: ", "tag": "con"})
            self.message_queue.put({"action": "log", "text": f"{con_text}\n\n"})
            self._speak_with_animation(con_text, "con", CHARACTERS["con"]["voice"])

            if not self.is_running:
                break
            time.sleep(2)

        # 討論終了、ジャッジ
        if len(self.history) >= 2:
            self._run_judge()

        self.message_queue.put({"action": "done"})

    def _speak_with_animation(self, text: str, speaker: str, voice: str):
        """音声再生と口パク"""
        self.message_queue.put({"action": "speaker", "speaker": speaker})

        # 音声ファイル生成
        with tempfile.NamedTemporaryFile(suffix='.aiff', delete=False) as f:
            audio_path = f.name

        try:
            subprocess.run(['say', '-v', voice, '-r', '150', '-o', audio_path, text],
                          check=True, capture_output=True)

            # 再生開始
            play_proc = subprocess.Popen(['afplay', audio_path],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 口パク
            while play_proc.poll() is None:
                self.message_queue.put({"action": "mouth", "open": True})
                time.sleep(0.1)
                self.message_queue.put({"action": "mouth", "open": False})
                time.sleep(0.1)

        finally:
            self.message_queue.put({"action": "mouth", "open": False})
            if os.path.exists(audio_path):
                os.remove(audio_path)

    def _run_judge(self):
        """ジャッジを実行"""
        pro_name = CHARACTERS["pro"]["name"]
        con_name = CHARACTERS["con"]["name"]

        self.message_queue.put({"action": "log", "text": "\n⚖️ ジャッジAI判定中...\n\n", "tag": "system"})

        judge_system = "あなたは公平なディベートの審判です。簡潔に評価してください。"
        judge_prompt = create_judge_prompt(self.topic, self.history, pro_name, con_name)

        try:
            result = get_groq_response(judge_prompt, judge_system, max_tokens=300)
            self.message_queue.put({"action": "log", "text": result + "\n", "tag": "judge"})
        except Exception as e:
            self.message_queue.put({"action": "log", "text": f"[判定エラー: {e}]\n", "tag": "system"})

    def run(self):
        """アプリ起動"""
        self.root.mainloop()


if __name__ == "__main__":
    app = DebateApp()
    app.run()
