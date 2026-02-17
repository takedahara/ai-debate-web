"""
AI Debate VOICEVOX版 - 美少女キャラ＋VOICEVOX音声
事前準備: VOICEVOXを起動しておく（http://localhost:50021）
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
import requests
import wave
import io


class RateLimitError(Exception):
    """API制限エラー"""
    pass


# バックエンド設定
BACKEND = "groq"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")  # 環境変数から取得

# VOICEVOX設定
VOICEVOX_URL = "http://localhost:50021"

# キャラクター設定（美少女版）
CHARACTERS = {
    "pro": {
        "name": "さくら",
        "age": "17歳",
        "job": "高校生",
        "tone": "元気で明るい口調",
        "personality": "ポジティブ、熱血、たまにドジ",
        "speaker_id": 3,  # ずんだもん
        "color": "#FF69B4",  # ホットピンク
    },
    "con": {
        "name": "あおい",
        "age": "18歳",
        "job": "大学生",
        "tone": "クールで知的な口調",
        "personality": "冷静、論理的、ちょっと毒舌",
        "speaker_id": 2,  # 四国めたん
        "color": "#87CEEB",  # スカイブルー
    },
    "judge": {
        "name": "ジャッジ",
        "speaker_id": 8,  # 春日部つむぎ
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


def check_voicevox() -> bool:
    """VOICEVOXが起動しているか確認"""
    try:
        response = requests.get(f"{VOICEVOX_URL}/speakers", timeout=2)
        return response.status_code == 200
    except:
        return False


def speak_voicevox(text: str, speaker_id: int) -> str:
    """VOICEVOXで音声合成し、一時ファイルのパスを返す"""
    # 音声クエリ作成
    query_response = requests.post(
        f"{VOICEVOX_URL}/audio_query",
        params={"text": text, "speaker": speaker_id},
        timeout=30
    )
    query_response.raise_for_status()
    query = query_response.json()

    # 速度調整
    query["speedScale"] = 1.2

    # 音声合成
    synthesis_response = requests.post(
        f"{VOICEVOX_URL}/synthesis",
        params={"speaker": speaker_id},
        json=query,
        timeout=60
    )
    synthesis_response.raise_for_status()

    # 一時ファイルに保存
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        f.write(synthesis_response.content)
        return f.name


def get_wav_duration(wav_path: str) -> float:
    """WAVファイルの長さを取得（秒）"""
    with wave.open(wav_path, 'r') as wav:
        frames = wav.getnframes()
        rate = wav.getframerate()
        return frames / float(rate)


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
- 自然な会話調で話す

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
勝者は○○さんです！

{pro_name}さんは○点、{con_name}さんは○点でした。

○○さんの「〜」という主張が特に説得力がありました。
お二人ともお疲れ様でした！"""


class DebateApp:
    """AI討論アプリケーション（VOICEVOX版）"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AI Debate - 美少女キャラ版")
        self.root.geometry("850x800")
        self.root.configure(bg='#1a1a2e')

        self.assets_dir = os.path.join(os.path.dirname(__file__), "assets")
        self._ensure_assets()

        self.images = {}
        self.current_speaker = None
        self.mouth_open = False
        self.is_running = False
        self.history = []
        self.topic = ""
        self.voicevox_available = False

        # メッセージキュー
        self.message_queue = queue.Queue()

        # 口パク用フラグ
        self.is_speaking = False

        self._setup_ui()
        self._load_images()
        self._check_voicevox()

        self.root.after(16, self._process_queue)
        self.root.after(80, self._animate_mouth)  # 口パク専用ループ

    def _check_voicevox(self):
        """VOICEVOX確認"""
        self.voicevox_available = check_voicevox()
        if self.voicevox_available:
            self.status_label.config(text="✅ VOICEVOX接続OK", fg="#90EE90")
        else:
            self.status_label.config(text="⚠️ VOICEVOXを起動してください", fg="#FFD700")

    def _ensure_assets(self):
        """画像を準備"""
        if not os.path.exists(self.assets_dir):
            os.makedirs(self.assets_dir)

        # カスタム画像がなければデフォルト生成
        for img_name in ["pro_closed.png", "pro_open.png", "con_closed.png", "con_open.png"]:
            img_path = os.path.join(self.assets_dir, img_name)
            if not os.path.exists(img_path):
                self._generate_character_image(img_name)

    def _generate_character_image(self, filename: str):
        """美少女風キャラクター画像を生成（プレースホルダー）"""
        size = 200
        img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        is_pro = filename.startswith("pro")
        is_open = "open" in filename

        if is_pro:
            # さくら（ピンク系）
            hair_color = (255, 182, 193)  # ライトピンク
            face_color = (255, 228, 225)  # ミスティローズ
            eye_color = (255, 105, 180)   # ホットピンク
        else:
            # あおい（ブルー系）
            hair_color = (135, 206, 250)  # ライトスカイブルー
            face_color = (255, 240, 245)  # ラベンダーブラッシュ
            eye_color = (100, 149, 237)   # コーンフラワーブルー

        # 髪（長髪風）
        draw.ellipse([15, 5, 185, 130], fill=hair_color)
        draw.ellipse([5, 50, 50, 190], fill=hair_color)
        draw.ellipse([150, 50, 195, 190], fill=hair_color)

        # 顔
        draw.ellipse([35, 35, 165, 175], fill=face_color)

        # 目（大きめ）
        eye_y = 80
        # 白目
        draw.ellipse([55, eye_y, 90, eye_y + 40], fill=(255, 255, 255))
        draw.ellipse([110, eye_y, 145, eye_y + 40], fill=(255, 255, 255))
        # 瞳
        draw.ellipse([62, eye_y + 8, 85, eye_y + 35], fill=eye_color)
        draw.ellipse([117, eye_y + 8, 140, eye_y + 35], fill=eye_color)
        # ハイライト
        draw.ellipse([65, eye_y + 10, 73, eye_y + 18], fill=(255, 255, 255))
        draw.ellipse([120, eye_y + 10, 128, eye_y + 18], fill=(255, 255, 255))
        # 小ハイライト
        draw.ellipse([75, eye_y + 22, 80, eye_y + 27], fill=(255, 255, 255))
        draw.ellipse([130, eye_y + 22, 135, eye_y + 27], fill=(255, 255, 255))

        # 眉
        draw.arc([55, eye_y - 15, 90, eye_y + 5], start=200, end=340, fill=(100, 80, 80), width=2)
        draw.arc([110, eye_y - 15, 145, eye_y + 5], start=200, end=340, fill=(100, 80, 80), width=2)

        # 鼻（小さく）
        draw.polygon([(100, 125), (97, 132), (103, 132)], fill=(255, 200, 200))

        # 口
        mouth_y = 145
        if is_open:
            # 開いた口（かわいく）
            draw.ellipse([85, mouth_y, 115, mouth_y + 18], fill=(255, 150, 150))
            draw.ellipse([90, mouth_y + 2, 110, mouth_y + 10], fill=(200, 80, 80))
        else:
            # 閉じた口（微笑み）
            draw.arc([85, mouth_y, 115, mouth_y + 12], start=0, end=180, fill=(255, 130, 130), width=2)

        # チーク
        draw.ellipse([45, 120, 65, 135], fill=(255, 200, 200, 150))
        draw.ellipse([135, 120, 155, 135], fill=(255, 200, 200, 150))

        img.save(os.path.join(self.assets_dir, filename))

    def _load_images(self):
        """画像をロード（アスペクト比を維持）"""
        max_size = 300  # 最大サイズ
        for key in ['pro_closed', 'pro_open', 'con_closed', 'con_open']:
            path = os.path.join(self.assets_dir, f"{key}.png")
            if os.path.exists(path):
                img = Image.open(path)
                # アスペクト比を維持してリサイズ
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                self.images[key] = ImageTk.PhotoImage(img)

    def _setup_ui(self):
        """UIを構築"""
        # タイトル
        title = tk.Label(self.root, text="✨ AI DEBATE ✨", font=("Helvetica", 22, "bold"),
                        bg='#1a1a2e', fg='#ff6b9d')
        title.pack(pady=8)

        # ステータス
        self.status_label = tk.Label(self.root, text="確認中...", font=("Helvetica", 10),
                                     bg='#1a1a2e', fg='gray')
        self.status_label.pack()

        # キャラクターエリア
        char_frame = tk.Frame(self.root, bg='#1a1a2e')
        char_frame.pack(pady=10)

        # 左キャラ
        self.pro_frame = tk.Frame(char_frame, bg='#1a1a2e')
        self.pro_frame.pack(side=tk.LEFT, padx=15)
        self.pro_canvas = Canvas(self.pro_frame, width=310, height=310, bg='#1a1a2e', highlightthickness=0)
        self.pro_canvas.pack()
        tk.Label(self.pro_frame, text=f"💖 {CHARACTERS['pro']['name']}", font=("Helvetica", 16, "bold"),
                bg='#1a1a2e', fg=CHARACTERS['pro']['color']).pack()

        # VS
        tk.Label(char_frame, text="⚔️", font=("Helvetica", 36),
                bg='#1a1a2e', fg='white').pack(side=tk.LEFT, padx=8)

        # 右キャラ
        self.con_frame = tk.Frame(char_frame, bg='#1a1a2e')
        self.con_frame.pack(side=tk.LEFT, padx=15)
        self.con_canvas = Canvas(self.con_frame, width=310, height=310, bg='#1a1a2e', highlightthickness=0)
        self.con_canvas.pack()
        tk.Label(self.con_frame, text=f"💙 {CHARACTERS['con']['name']}", font=("Helvetica", 16, "bold"),
                bg='#1a1a2e', fg=CHARACTERS['con']['color']).pack()

        # 議題表示
        self.topic_label = tk.Label(self.root, text="", font=("Helvetica", 13),
                                    bg='#1a1a2e', fg='#00d4ff', wraplength=550)
        self.topic_label.pack(pady=8)

        # 会話ログ
        log_frame = tk.Frame(self.root, bg='#1a1a2e')
        log_frame.pack(pady=8, fill=tk.BOTH, expand=True, padx=20)

        self.log_text = tk.Text(log_frame, height=10, width=65, font=("Helvetica", 11),
                               bg='#16213e', fg='white', wrap=tk.WORD, relief=tk.FLAT)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

        # タグ設定
        self.log_text.tag_configure("pro", foreground=CHARACTERS['pro']['color'])
        self.log_text.tag_configure("con", foreground=CHARACTERS['con']['color'])
        self.log_text.tag_configure("system", foreground="#00d4ff")
        self.log_text.tag_configure("judge", foreground="#FFD700")

        # ボタンエリア
        btn_frame = tk.Frame(self.root, bg='#1a1a2e')
        btn_frame.pack(pady=12)

        self.start_btn = tk.Button(btn_frame, text="開始", font=("Helvetica", 14),
                                   command=self._start_debate, width=10)
        self.start_btn.pack(side=tk.LEFT, padx=10)

        self.stop_btn = tk.Button(btn_frame, text="終了＆判定", font=("Helvetica", 14),
                                  command=self._stop_debate, state=tk.DISABLED, width=10)
        self.stop_btn.pack(side=tk.LEFT, padx=10)

        refresh_btn = tk.Button(btn_frame, text="再接続", font=("Helvetica", 12),
                               command=self._check_voicevox, width=6)
        refresh_btn.pack(side=tk.LEFT, padx=5)

        # 初期描画
        self._draw_characters()

    def _draw_characters(self):
        """キャラクターを描画"""
        self.pro_canvas.delete("all")
        self.con_canvas.delete("all")

        # 賛成派
        pro_key = 'pro_open' if (self.current_speaker == 'pro' and self.mouth_open) else 'pro_closed'
        if pro_key in self.images:
            self.pro_canvas.create_image(155, 155, image=self.images[pro_key])
        if self.current_speaker == 'pro':
            self.pro_canvas.create_oval(2, 2, 308, 308, outline=CHARACTERS['pro']['color'], width=4)

        # 反対派
        con_key = 'con_open' if (self.current_speaker == 'con' and self.mouth_open) else 'con_closed'
        if con_key in self.images:
            self.con_canvas.create_image(155, 155, image=self.images[con_key])
        if self.current_speaker == 'con':
            self.con_canvas.create_oval(2, 2, 308, 308, outline=CHARACTERS['con']['color'], width=4)

    def _animate_mouth(self):
        """口パク専用アニメーションループ（メインスレッドで直接実行）"""
        if self.is_speaking:
            self.mouth_open = not self.mouth_open
            self._draw_characters()
        self.root.after(80, self._animate_mouth)  # 約12fps で口パク

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
                elif action == "speaking":
                    self.is_speaking = msg["value"]
                    if not self.is_speaking:
                        self.mouth_open = False
                        self._draw_characters()
                elif action == "done":
                    self.is_running = False
                    self.is_speaking = False
                    self.start_btn.config(state=tk.NORMAL)
                    self.stop_btn.config(state=tk.DISABLED)
                    self.current_speaker = None
                    self._draw_characters()

        except queue.Empty:
            pass

        self.root.after(50, self._process_queue)

    def _start_debate(self):
        """討論開始"""
        if not self.voicevox_available:
            self._check_voicevox()
            if not self.voicevox_available:
                self.log_text.insert(tk.END, "⚠️ VOICEVOXを起動してから開始してください\n", "system")
                return

        topic = simpledialog.askstring("議題", "議題を入力してください:",
                                       initialvalue="AIは人間の仕事を奪う")
        if not topic:
            return

        self.topic = topic
        self.history = []
        self.topic_label.config(text=f"📢 議題: 「{topic}」")
        self.log_text.delete(1.0, tk.END)

        self.is_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        thread = threading.Thread(target=self._debate_loop, daemon=True)
        thread.start()

    def _stop_debate(self):
        """討論終了"""
        self.is_running = False
        self.stop_btn.config(state=tk.DISABLED)

    def _generate_text_and_audio(self, prompt: str, system: str, speaker_id: int):
        """テキスト生成と音声生成を連続で行う"""
        text = get_groq_response(prompt, system).strip()
        wav_path = speak_voicevox(text, speaker_id)
        return text, wav_path

    def _debate_loop(self):
        """討論ループ（テキスト＋音声の先読み最適化版）"""
        from concurrent.futures import ThreadPoolExecutor

        pro_name = CHARACTERS["pro"]["name"]
        con_name = CHARACTERS["con"]["name"]

        pro_system = create_debater_prompt("pro", self.topic, CHARACTERS["pro"])
        con_system = create_debater_prompt("con", self.topic, CHARACTERS["con"])

        initial_prompt = f"「{self.topic}」について、具体例を一つ挙げて自分の意見を言って。"

        executor = ThreadPoolExecutor(max_workers=2)
        turn = 0
        next_future = None  # (text, wav_path) を返す

        while self.is_running:
            turn += 1

            # === 賛成派の発言 ===
            if turn == 1:
                # 初回は同期で生成
                try:
                    pro_text = get_groq_response(initial_prompt, pro_system).strip()
                    pro_wav = speak_voicevox(pro_text, CHARACTERS["pro"]["speaker_id"])
                except Exception as e:
                    self.message_queue.put({"action": "log", "text": f"\n[エラー: {e}]\n", "tag": "system"})
                    break
            else:
                # 先読み結果を取得
                try:
                    pro_text, pro_wav = next_future.result()
                except Exception as e:
                    self.message_queue.put({"action": "log", "text": f"\n[エラー: {e}]\n", "tag": "system"})
                    break

            self.history.append(pro_text)
            self.message_queue.put({"action": "log", "text": f"{pro_name}: ", "tag": "pro"})
            self.message_queue.put({"action": "log", "text": f"{pro_text}\n\n"})

            # 反対派のテキスト＋音声を先読み開始
            con_prompt = f"{pro_name}「{pro_text}」\n\n↑この主張に反論して。"
            next_future = executor.submit(
                self._generate_text_and_audio,
                con_prompt, con_system, CHARACTERS["con"]["speaker_id"]
            )

            # 賛成派の音声再生（既に生成済み）
            self._play_with_animation(pro_wav, "pro")

            if not self.is_running:
                break

            # === 反対派の発言 ===
            try:
                con_text, con_wav = next_future.result()
            except Exception as e:
                self.message_queue.put({"action": "log", "text": f"\n[エラー: {e}]\n", "tag": "system"})
                break

            self.history.append(con_text)
            self.message_queue.put({"action": "log", "text": f"{con_name}: ", "tag": "con"})
            self.message_queue.put({"action": "log", "text": f"{con_text}\n\n"})

            # 賛成派のテキスト＋音声を先読み開始
            pro_prompt = f"{con_name}「{con_text}」\n\n↑この主張に反論して。"
            next_future = executor.submit(
                self._generate_text_and_audio,
                pro_prompt, pro_system, CHARACTERS["pro"]["speaker_id"]
            )

            # 反対派の音声再生（既に生成済み）
            self._play_with_animation(con_wav, "con")

            if not self.is_running:
                break

        executor.shutdown(wait=False)

        # ジャッジ
        if len(self.history) >= 2:
            self._run_judge()

        self.message_queue.put({"action": "done"})

    def _play_with_animation(self, wav_path: str, speaker: str):
        """音声ファイル再生と口パク（音声は生成済み）"""
        self.message_queue.put({"action": "speaker", "speaker": speaker})
        self.message_queue.put({"action": "speaking", "value": True})

        try:
            # 再生開始（同期で待つ）
            play_proc = subprocess.Popen(['afplay', wav_path],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            play_proc.wait()

        except Exception as e:
            self.message_queue.put({"action": "log", "text": f"[再生エラー: {e}]\n", "tag": "system"})

        finally:
            self.message_queue.put({"action": "speaking", "value": False})
            # クリーンアップ
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def _speak_with_animation(self, text: str, speaker: str, speaker_id: int):
        """VOICEVOX音声再生と口パク"""
        self.message_queue.put({"action": "speaker", "speaker": speaker})

        try:
            # VOICEVOX音声生成
            wav_path = speak_voicevox(text, speaker_id)
            duration = get_wav_duration(wav_path)

            # 再生開始
            play_proc = subprocess.Popen(['afplay', wav_path],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 口パク
            start_time = time.time()
            while play_proc.poll() is None and (time.time() - start_time) < duration + 1:
                self.message_queue.put({"action": "mouth", "open": True})
                time.sleep(0.12)
                self.message_queue.put({"action": "mouth", "open": False})
                time.sleep(0.08)

            play_proc.wait()

            # クリーンアップ
            if os.path.exists(wav_path):
                os.remove(wav_path)

        except Exception as e:
            self.message_queue.put({"action": "log", "text": f"[音声エラー: {e}]\n", "tag": "system"})

        finally:
            self.message_queue.put({"action": "mouth", "open": False})

    def _run_judge(self):
        """ジャッジを実行（音声付き）"""
        pro_name = CHARACTERS["pro"]["name"]
        con_name = CHARACTERS["con"]["name"]

        self.message_queue.put({"action": "log", "text": "\n⚖️ ジャッジタイム！\n\n", "tag": "system"})

        judge_system = "あなたは明るく元気なディベートの審判です。かわいく判定結果を発表してください。"
        judge_prompt = create_judge_prompt(self.topic, self.history, pro_name, con_name)

        try:
            result = get_groq_response(judge_prompt, judge_system, max_tokens=300)
            self.message_queue.put({"action": "log", "text": f"👩‍⚖️ {result}\n", "tag": "judge"})

            # ジャッジの音声読み上げ
            self.message_queue.put({"action": "speaker", "speaker": None})
            wav_path = speak_voicevox(result, CHARACTERS["judge"]["speaker_id"])

            play_proc = subprocess.Popen(['afplay', wav_path],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            play_proc.wait()

            if os.path.exists(wav_path):
                os.remove(wav_path)

        except Exception as e:
            self.message_queue.put({"action": "log", "text": f"[判定エラー: {e}]\n", "tag": "system"})

    def run(self):
        """アプリ起動"""
        self.root.mainloop()


if __name__ == "__main__":
    print("=" * 50)
    print("AI Debate VOICEVOX版")
    print("=" * 50)
    print("\n⚠️  VOICEVOXを起動してから実行してください")
    print("   ダウンロード: https://voicevox.hiroshiba.jp/\n")

    app = DebateApp()
    app.run()
