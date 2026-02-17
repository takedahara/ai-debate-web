"""
AI Debate YouTube版 - 動画配信向け全部入りバージョン
機能:
- 表情変化（通常、怒り、笑顔、驚き）
- 字幕表示（リアルタイムテロップ）
- BGM・効果音
- 勝敗演出
- 背景アニメーション
"""

import tkinter as tk
from tkinter import Canvas, simpledialog
from PIL import Image, ImageDraw, ImageTk, ImageFilter
import os
import threading
import subprocess
import tempfile
import time
import queue
import requests
import wave
import random
import math


class RateLimitError(Exception):
    pass


# API設定
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")  # 環境変数から取得
VOICEVOX_URL = "http://localhost:50021"

# BGM・効果音設定（ファイルがあれば再生）
SOUND_DIR = os.path.join(os.path.dirname(__file__), "sounds")
SOUNDS = {
    "bgm": "bgm.mp3",           # 討論中のBGM
    "start": "start.mp3",       # 開始時の効果音
    "round": "round.mp3",       # ラウンド開始
    "judge": "judge.mp3",       # ジャッジ開始
    "winner": "winner.mp3",     # 勝者発表
}

# キャラクター設定
CHARACTERS = {
    "pro": {
        "name": "さくら",
        "age": "17歳",
        "job": "高校生",
        "tone": "元気で明るい口調",
        "personality": "ポジティブ、熱血、たまにドジ",
        "speaker_id": 3,
        "color": "#FF69B4",
        "bg_color": "#FFE4E1",
    },
    "con": {
        "name": "あおい",
        "age": "18歳",
        "job": "大学生",
        "tone": "クールで知的な口調",
        "personality": "冷静、論理的、ちょっと毒舌",
        "speaker_id": 2,
        "color": "#4169E1",
        "bg_color": "#E6E6FA",
    },
    "judge": {
        "name": "ジャッジ",
        "speaker_id": 8,
    }
}

# 表情リスト
EXPRESSIONS = ["normal", "angry", "happy", "surprised"]


def get_groq_response(prompt: str, system_prompt: str, max_tokens: int = 200) -> str:
    """Groq APIを使用"""
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)

    for attempt in range(3):
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
            if "rate" in str(e).lower() or "429" in str(e):
                time.sleep(5 * (attempt + 1))
                continue
            raise
    raise RateLimitError("API制限")


def check_voicevox() -> bool:
    try:
        return requests.get(f"{VOICEVOX_URL}/speakers", timeout=2).status_code == 200
    except:
        return False


def speak_voicevox(text: str, speaker_id: int) -> str:
    """VOICEVOX音声合成"""
    query = requests.post(
        f"{VOICEVOX_URL}/audio_query",
        params={"text": text, "speaker": speaker_id}, timeout=30
    ).json()
    query["speedScale"] = 1.2

    audio = requests.post(
        f"{VOICEVOX_URL}/synthesis",
        params={"speaker": speaker_id}, json=query, timeout=60
    ).content

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        f.write(audio)
        return f.name


def get_wav_duration(wav_path: str) -> float:
    with wave.open(wav_path, 'r') as wav:
        return wav.getnframes() / float(wav.getframerate())


class SoundManager:
    """BGM・効果音管理"""
    def __init__(self):
        self.bgm_process = None
        self.sounds_available = os.path.exists(SOUND_DIR)
        if not self.sounds_available:
            os.makedirs(SOUND_DIR, exist_ok=True)

    def play_sound(self, sound_key: str, loop: bool = False):
        """効果音を再生"""
        if sound_key not in SOUNDS:
            return
        path = os.path.join(SOUND_DIR, SOUNDS[sound_key])
        if not os.path.exists(path):
            return
        try:
            if loop:
                # BGMはループ再生（afplayの--loop）
                self.bgm_process = subprocess.Popen(
                    ['afplay', path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            else:
                subprocess.Popen(
                    ['afplay', path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
        except:
            pass

    def stop_bgm(self):
        """BGM停止"""
        if self.bgm_process:
            try:
                self.bgm_process.terminate()
            except:
                pass
            self.bgm_process = None

    def play_bgm(self):
        """BGM開始"""
        self.stop_bgm()
        self.play_sound("bgm", loop=True)


sound_manager = SoundManager()


def analyze_emotion(text: str) -> str:
    """テキストから感情を推定"""
    angry_words = ["違う", "おかしい", "間違", "反論", "そんな", "ありえない", "バカ", "無理"]
    happy_words = ["そうだ", "いい", "素晴らしい", "確かに", "賛成", "嬉しい", "楽しい", "最高"]
    surprised_words = ["え？", "まさか", "本当", "驚", "信じられない", "すごい", "！？"]

    for word in angry_words:
        if word in text:
            return "angry"
    for word in surprised_words:
        if word in text:
            return "surprised"
    for word in happy_words:
        if word in text:
            return "happy"
    return "normal"


def create_debater_prompt(role: str, topic: str, personality: dict) -> str:
    stance = "賛成" if role == "pro" else "反対"
    return f"""あなたは{personality['name']}という名前の{personality['age']}の{personality['job']}です。
「{topic}」に{stance}の立場で議論しています。

【話し方】
- 一文〜二文で返答
- {personality['tone']}で話す
- 感情豊かに話す（怒ったり、驚いたり、喜んだり）

性格: {personality['personality']}"""


def create_judge_prompt(topic: str, history: list, pro_name: str, con_name: str) -> str:
    conversation = "\n".join([
        f"{pro_name if i % 2 == 0 else con_name}: {msg}"
        for i, msg in enumerate(history)
    ])
    return f"""【議題】{topic}

【議論】
{conversation}

【判定を発表してください】
「勝者は○○さん！」から始めて、理由を簡潔に述べてください。"""


class Particle:
    """パーティクルエフェクト用"""
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.vx = random.uniform(-3, 3)
        self.vy = random.uniform(-5, -1)
        self.life = 1.0
        self.color = color
        self.size = random.randint(3, 8)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.2  # 重力
        self.life -= 0.02
        return self.life > 0


class YouTubeDebateApp:
    """YouTube向けAI討論アプリ"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AI Debate - YouTube Edition")
        self.root.geometry("1280x720")
        self.root.configure(bg='#1a1a2e')

        self.assets_dir = os.path.join(os.path.dirname(__file__), "assets_youtube")
        self._ensure_assets()

        self.images = {}
        self.current_speaker = None
        self.current_expression = {"pro": "normal", "con": "normal"}
        self.mouth_open = False
        self.is_running = False
        self.is_speaking = False
        self.history = []
        self.topic = ""
        self.particles = []
        self.subtitle_text = ""
        self.subtitle_speaker = None
        self.bg_offset = 0
        self.round_num = 0

        self.message_queue = queue.Queue()

        self._setup_ui()
        self._load_images()
        self._check_voicevox()

        # アニメーションループ
        self.root.after(16, self._process_queue)
        self.root.after(80, self._animate_mouth)
        self.root.after(50, self._animate_background)
        self.root.after(30, self._animate_particles)

    def _ensure_assets(self):
        """画像アセット準備"""
        if not os.path.exists(self.assets_dir):
            os.makedirs(self.assets_dir)

        # 全表情パターンの画像を生成
        for char in ["pro", "con"]:
            for expr in EXPRESSIONS:
                for mouth in ["closed", "open"]:
                    filename = f"{char}_{expr}_{mouth}.png"
                    path = os.path.join(self.assets_dir, filename)
                    if not os.path.exists(path):
                        self._generate_character_image(filename)

    def _generate_character_image(self, filename: str):
        """表情付きキャラクター画像を生成"""
        size = 300
        img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        parts = filename.replace(".png", "").split("_")
        is_pro = parts[0] == "pro"
        expression = parts[1]
        is_open = parts[2] == "open"

        # 色設定
        if is_pro:
            hair_color = (255, 182, 193)
            face_color = (255, 228, 225)
            eye_color = (255, 105, 180)
        else:
            hair_color = (135, 206, 250)
            face_color = (255, 240, 245)
            eye_color = (100, 149, 237)

        # 髪
        draw.ellipse([25, 10, 275, 180], fill=hair_color)
        draw.ellipse([10, 70, 70, 280], fill=hair_color)
        draw.ellipse([230, 70, 290, 280], fill=hair_color)

        # 顔
        draw.ellipse([50, 50, 250, 260], fill=face_color)

        # 目の位置
        eye_y = 120
        left_eye_x, right_eye_x = 95, 175

        # 表情による目の変化
        if expression == "angry":
            # 怒り - つり上がった眉、細い目
            draw.polygon([(left_eye_x-20, eye_y-20), (left_eye_x+30, eye_y-35),
                         (left_eye_x+30, eye_y-25), (left_eye_x-20, eye_y-10)], fill=(80, 60, 60))
            draw.polygon([(right_eye_x+50, eye_y-20), (right_eye_x, eye_y-35),
                         (right_eye_x, eye_y-25), (right_eye_x+50, eye_y-10)], fill=(80, 60, 60))
            draw.ellipse([left_eye_x, eye_y, left_eye_x+40, eye_y+25], fill=(255, 255, 255))
            draw.ellipse([right_eye_x, eye_y, right_eye_x+40, eye_y+25], fill=(255, 255, 255))
            draw.ellipse([left_eye_x+10, eye_y+5, left_eye_x+32, eye_y+22], fill=eye_color)
            draw.ellipse([right_eye_x+10, eye_y+5, right_eye_x+32, eye_y+22], fill=eye_color)

        elif expression == "happy":
            # 笑顔 - 閉じた笑い目
            draw.arc([left_eye_x, eye_y, left_eye_x+40, eye_y+30], start=200, end=340,
                    fill=(80, 60, 60), width=4)
            draw.arc([right_eye_x, eye_y, right_eye_x+40, eye_y+30], start=200, end=340,
                    fill=(80, 60, 60), width=4)

        elif expression == "surprised":
            # 驚き - 大きな丸い目
            draw.ellipse([left_eye_x-5, eye_y-10, left_eye_x+50, eye_y+50], fill=(255, 255, 255))
            draw.ellipse([right_eye_x-5, eye_y-10, right_eye_x+50, eye_y+50], fill=(255, 255, 255))
            draw.ellipse([left_eye_x+8, eye_y+2, left_eye_x+38, eye_y+38], fill=eye_color)
            draw.ellipse([right_eye_x+8, eye_y+2, right_eye_x+38, eye_y+38], fill=eye_color)
            draw.ellipse([left_eye_x+15, eye_y+8, left_eye_x+25, eye_y+18], fill=(255, 255, 255))
            draw.ellipse([right_eye_x+15, eye_y+8, right_eye_x+25, eye_y+18], fill=(255, 255, 255))

        else:  # normal
            draw.ellipse([left_eye_x, eye_y, left_eye_x+45, eye_y+45], fill=(255, 255, 255))
            draw.ellipse([right_eye_x, eye_y, right_eye_x+45, eye_y+45], fill=(255, 255, 255))
            draw.ellipse([left_eye_x+10, eye_y+8, left_eye_x+38, eye_y+38], fill=eye_color)
            draw.ellipse([right_eye_x+10, eye_y+8, right_eye_x+38, eye_y+38], fill=eye_color)
            draw.ellipse([left_eye_x+18, eye_y+12, left_eye_x+28, eye_y+22], fill=(255, 255, 255))
            draw.ellipse([right_eye_x+18, eye_y+12, right_eye_x+28, eye_y+22], fill=(255, 255, 255))

        # 口
        mouth_y = 200
        if expression == "angry":
            if is_open:
                draw.polygon([(120, mouth_y), (150, mouth_y+25), (180, mouth_y)], fill=(200, 80, 80))
            else:
                draw.line([(120, mouth_y+5), (180, mouth_y+5)], fill=(150, 80, 80), width=3)
        elif expression == "happy":
            if is_open:
                draw.chord([110, mouth_y-10, 190, mouth_y+30], start=0, end=180, fill=(255, 150, 150))
            else:
                draw.arc([110, mouth_y-5, 190, mouth_y+20], start=0, end=180, fill=(255, 130, 130), width=3)
        elif expression == "surprised":
            draw.ellipse([135, mouth_y, 165, mouth_y+35], fill=(200, 100, 100))
        else:  # normal
            if is_open:
                draw.ellipse([125, mouth_y, 175, mouth_y+25], fill=(255, 150, 150))
            else:
                draw.arc([125, mouth_y, 175, mouth_y+18], start=0, end=180, fill=(255, 130, 130), width=2)

        # チーク
        if expression == "happy":
            draw.ellipse([60, 160, 95, 185], fill=(255, 180, 180, 200))
            draw.ellipse([205, 160, 240, 185], fill=(255, 180, 180, 200))
        else:
            draw.ellipse([65, 165, 95, 185], fill=(255, 200, 200, 150))
            draw.ellipse([205, 165, 235, 185], fill=(255, 200, 200, 150))

        img.save(os.path.join(self.assets_dir, filename))

    def _load_images(self):
        """画像をロード"""
        max_size = 280
        for char in ["pro", "con"]:
            for expr in EXPRESSIONS:
                for mouth in ["closed", "open"]:
                    key = f"{char}_{expr}_{mouth}"
                    path = os.path.join(self.assets_dir, f"{key}.png")
                    if os.path.exists(path):
                        img = Image.open(path)
                        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                        self.images[key] = ImageTk.PhotoImage(img)

    def _check_voicevox(self):
        self.voicevox_available = check_voicevox()
        status = "✅ VOICEVOX OK" if self.voicevox_available else "⚠️ VOICEVOX未接続"
        color = "#90EE90" if self.voicevox_available else "#FFD700"
        self.status_label.config(text=status, fg=color)

    def _setup_ui(self):
        """UI構築"""
        # メインキャンバス（背景 + キャラ + エフェクト）
        self.main_canvas = Canvas(self.root, width=1280, height=720, bg='#1a1a2e', highlightthickness=0)
        self.main_canvas.pack()

        # ステータス
        self.status_label = tk.Label(self.root, text="確認中...", font=("Helvetica", 10),
                                     bg='#1a1a2e', fg='gray')
        self.status_label.place(x=10, y=10)

        # ラウンド表示
        self.round_label = tk.Label(self.root, text="", font=("Helvetica", 18, "bold"),
                                    bg='#1a1a2e', fg='#FFD700')
        self.round_label.place(x=640, y=15, anchor='n')

        # ボタン
        btn_frame = tk.Frame(self.root, bg='#1a1a2e')
        btn_frame.place(x=640, y=680, anchor='center')

        self.start_btn = tk.Button(btn_frame, text="討論開始", font=("Helvetica", 14),
                                   command=self._start_debate, width=12)
        self.start_btn.pack(side=tk.LEFT, padx=10)

        self.stop_btn = tk.Button(btn_frame, text="終了＆判定", font=("Helvetica", 14),
                                  command=self._stop_debate, state=tk.DISABLED, width=12)
        self.stop_btn.pack(side=tk.LEFT, padx=10)

        # 初期描画
        self._draw_scene()

    def _draw_scene(self):
        """シーン全体を描画"""
        self.main_canvas.delete("all")

        # 背景グラデーション
        for i in range(720):
            ratio = i / 720
            r = int(26 + (50 - 26) * ratio + 10 * math.sin(self.bg_offset + i * 0.01))
            g = int(26 + (30 - 26) * ratio + 10 * math.sin(self.bg_offset + i * 0.01 + 2))
            b = int(46 + (80 - 46) * ratio + 10 * math.sin(self.bg_offset + i * 0.01 + 4))
            r, g, b = max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
            color = f'#{r:02x}{g:02x}{b:02x}'
            self.main_canvas.create_line(0, i, 1280, i, fill=color)

        # VS テキスト
        self.main_canvas.create_text(640, 300, text="VS", font=("Helvetica", 72, "bold"),
                                     fill='#FFD700')

        # キャラクター枠
        # 左（賛成派）
        self.main_canvas.create_rectangle(80, 120, 400, 500, outline=CHARACTERS['pro']['color'], width=4)
        self.main_canvas.create_rectangle(80, 500, 400, 550, fill=CHARACTERS['pro']['color'], outline='')
        self.main_canvas.create_text(240, 525, text=f"💖 {CHARACTERS['pro']['name']}",
                                     font=("Helvetica", 18, "bold"), fill='white')

        # 右（反対派）
        self.main_canvas.create_rectangle(880, 120, 1200, 500, outline=CHARACTERS['con']['color'], width=4)
        self.main_canvas.create_rectangle(880, 500, 1200, 550, fill=CHARACTERS['con']['color'], outline='')
        self.main_canvas.create_text(1040, 525, text=f"💙 {CHARACTERS['con']['name']}",
                                     font=("Helvetica", 18, "bold"), fill='white')

        # キャラクター画像
        pro_expr = self.current_expression["pro"]
        con_expr = self.current_expression["con"]
        pro_mouth = "open" if (self.current_speaker == "pro" and self.mouth_open) else "closed"
        con_mouth = "open" if (self.current_speaker == "con" and self.mouth_open) else "closed"

        pro_key = f"pro_{pro_expr}_{pro_mouth}"
        con_key = f"con_{con_expr}_{con_mouth}"

        if pro_key in self.images:
            self.main_canvas.create_image(240, 310, image=self.images[pro_key])
        if con_key in self.images:
            self.main_canvas.create_image(1040, 310, image=self.images[con_key])

        # スピーカーハイライト
        if self.current_speaker == "pro":
            self.main_canvas.create_rectangle(75, 115, 405, 555, outline='#FFFF00', width=6)
        elif self.current_speaker == "con":
            self.main_canvas.create_rectangle(875, 115, 1205, 555, outline='#FFFF00', width=6)

        # 議題表示
        if self.topic:
            self.main_canvas.create_rectangle(200, 50, 1080, 100, fill='#2d2d5a', outline='#FFD700', width=2)
            self.main_canvas.create_text(640, 75, text=f"📢 {self.topic}",
                                        font=("Helvetica", 20, "bold"), fill='white')

        # 字幕表示
        if self.subtitle_text:
            # 字幕背景
            self.main_canvas.create_rectangle(100, 570, 1180, 650, fill='#000000', stipple='gray50')
            # 話者名
            if self.subtitle_speaker:
                speaker_color = CHARACTERS[self.subtitle_speaker]['color']
                speaker_name = CHARACTERS[self.subtitle_speaker]['name']
                self.main_canvas.create_text(150, 590, text=f"【{speaker_name}】",
                                            font=("Helvetica", 16, "bold"), fill=speaker_color, anchor='w')
            # 字幕テキスト
            self.main_canvas.create_text(640, 620, text=self.subtitle_text,
                                        font=("Helvetica", 22), fill='white', width=1000)

        # パーティクル
        for p in self.particles:
            alpha = int(p.life * 255)
            self.main_canvas.create_oval(p.x - p.size, p.y - p.size,
                                         p.x + p.size, p.y + p.size,
                                         fill=p.color, outline='')

    def _animate_background(self):
        """背景アニメーション"""
        self.bg_offset += 0.05
        if self.is_running or self.particles:
            self._draw_scene()
        self.root.after(50, self._animate_background)

    def _animate_mouth(self):
        """口パクアニメーション"""
        if self.is_speaking:
            self.mouth_open = not self.mouth_open
            self._draw_scene()
        self.root.after(80, self._animate_mouth)

    def _animate_particles(self):
        """パーティクルアニメーション"""
        self.particles = [p for p in self.particles if p.update()]
        if self.particles:
            self._draw_scene()
        self.root.after(30, self._animate_particles)

    def _spawn_particles(self, x, y, color, count=20):
        """パーティクル生成"""
        for _ in range(count):
            self.particles.append(Particle(x, y, color))

    def _process_queue(self):
        """メッセージキュー処理"""
        try:
            while True:
                msg = self.message_queue.get_nowait()
                action = msg.get("action")

                if action == "speaker":
                    self.current_speaker = msg["speaker"]
                    self._draw_scene()
                elif action == "expression":
                    self.current_expression[msg["speaker"]] = msg["value"]
                    self._draw_scene()
                elif action == "speaking":
                    self.is_speaking = msg["value"]
                    if not self.is_speaking:
                        self.mouth_open = False
                        self._draw_scene()
                elif action == "subtitle":
                    self.subtitle_text = msg["text"]
                    self.subtitle_speaker = msg.get("speaker")
                    self._draw_scene()
                elif action == "round":
                    self.round_num = msg["value"]
                    self.round_label.config(text=f"🔔 Round {self.round_num}")
                    sound_manager.play_sound("round")
                elif action == "particles":
                    self._spawn_particles(msg["x"], msg["y"], msg["color"], msg.get("count", 30))
                elif action == "judge_start":
                    self.round_label.config(text="⚖️ ジャッジタイム！")
                    self._spawn_particles(640, 360, "#FFD700", 50)
                    sound_manager.stop_bgm()
                    sound_manager.play_sound("judge")
                elif action == "winner":
                    sound_manager.play_sound("winner")
                elif action == "done":
                    self.is_running = False
                    self.is_speaking = False
                    self.start_btn.config(state=tk.NORMAL)
                    self.stop_btn.config(state=tk.DISABLED)
                    self.current_speaker = None
                    self.subtitle_text = ""
                    sound_manager.stop_bgm()
                    self._draw_scene()

        except queue.Empty:
            pass

        self.root.after(16, self._process_queue)

    def _start_debate(self):
        """討論開始"""
        if not self.voicevox_available:
            self._check_voicevox()
            if not self.voicevox_available:
                return

        topic = simpledialog.askstring("議題", "議題を入力してください:",
                                       initialvalue="AIは人間の仕事を奪う")
        if not topic:
            return

        self.topic = topic
        self.history = []
        self.round_num = 0

        self.is_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        self._draw_scene()

        # 開始効果音 & BGM
        sound_manager.play_sound("start")
        time.sleep(0.5)
        sound_manager.play_bgm()

        thread = threading.Thread(target=self._debate_loop, daemon=True)
        thread.start()

    def _stop_debate(self):
        self.is_running = False
        self.stop_btn.config(state=tk.DISABLED)

    def _generate_text_and_audio(self, prompt: str, system: str, speaker_id: int):
        """テキスト＋音声生成"""
        text = get_groq_response(prompt, system).strip()
        wav_path = speak_voicevox(text, speaker_id)
        return text, wav_path

    def _debate_loop(self):
        """討論ループ"""
        from concurrent.futures import ThreadPoolExecutor

        pro_name = CHARACTERS["pro"]["name"]
        con_name = CHARACTERS["con"]["name"]
        pro_system = create_debater_prompt("pro", self.topic, CHARACTERS["pro"])
        con_system = create_debater_prompt("con", self.topic, CHARACTERS["con"])

        initial_prompt = f"「{self.topic}」について、自分の意見を言って。"
        executor = ThreadPoolExecutor(max_workers=2)
        next_future = None

        while self.is_running:
            self.round_num += 1
            self.message_queue.put({"action": "round", "value": self.round_num})

            # === 賛成派 ===
            if self.round_num == 1:
                try:
                    pro_text = get_groq_response(initial_prompt, pro_system).strip()
                    pro_wav = speak_voicevox(pro_text, CHARACTERS["pro"]["speaker_id"])
                except Exception as e:
                    self.message_queue.put({"action": "subtitle", "text": f"[エラー: {e}]"})
                    break
            else:
                try:
                    pro_text, pro_wav = next_future.result()
                except Exception as e:
                    self.message_queue.put({"action": "subtitle", "text": f"[エラー: {e}]"})
                    break

            self.history.append(pro_text)
            emotion = analyze_emotion(pro_text)
            self.message_queue.put({"action": "expression", "speaker": "pro", "value": emotion})
            self.message_queue.put({"action": "subtitle", "text": pro_text, "speaker": "pro"})

            # 先読み開始
            con_prompt = f"{pro_name}「{pro_text}」\n\n↑反論して。"
            next_future = executor.submit(
                self._generate_text_and_audio,
                con_prompt, con_system, CHARACTERS["con"]["speaker_id"]
            )

            self._play_with_animation(pro_wav, "pro")
            if not self.is_running:
                break

            # === 反対派 ===
            try:
                con_text, con_wav = next_future.result()
            except Exception as e:
                self.message_queue.put({"action": "subtitle", "text": f"[エラー: {e}]"})
                break

            self.history.append(con_text)
            emotion = analyze_emotion(con_text)
            self.message_queue.put({"action": "expression", "speaker": "con", "value": emotion})
            self.message_queue.put({"action": "subtitle", "text": con_text, "speaker": "con"})

            # 先読み開始
            pro_prompt = f"{con_name}「{con_text}」\n\n↑反論して。"
            next_future = executor.submit(
                self._generate_text_and_audio,
                pro_prompt, pro_system, CHARACTERS["pro"]["speaker_id"]
            )

            self._play_with_animation(con_wav, "con")
            if not self.is_running:
                break

        executor.shutdown(wait=False)

        if len(self.history) >= 2:
            self._run_judge()

        self.message_queue.put({"action": "done"})

    def _play_with_animation(self, wav_path: str, speaker: str):
        """音声再生＋アニメーション"""
        self.message_queue.put({"action": "speaker", "speaker": speaker})
        self.message_queue.put({"action": "speaking", "value": True})

        try:
            play_proc = subprocess.Popen(['afplay', wav_path],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            play_proc.wait()
        finally:
            self.message_queue.put({"action": "speaking", "value": False})
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def _run_judge(self):
        """ジャッジ実行"""
        pro_name = CHARACTERS["pro"]["name"]
        con_name = CHARACTERS["con"]["name"]

        self.message_queue.put({"action": "judge_start"})
        self.message_queue.put({"action": "subtitle", "text": "⚖️ 判定中..."})

        judge_system = "あなたは元気なディベートの審判です。判定を発表してください。"
        judge_prompt = create_judge_prompt(self.topic, self.history, pro_name, con_name)

        try:
            result = get_groq_response(judge_prompt, judge_system, max_tokens=300)
            self.message_queue.put({"action": "subtitle", "text": result})

            # 勝者演出
            self.message_queue.put({"action": "winner"})
            time.sleep(0.3)
            if pro_name in result[:50]:
                self.message_queue.put({"action": "particles", "x": 240, "y": 310, "color": "#FF69B4", "count": 100})
            elif con_name in result[:50]:
                self.message_queue.put({"action": "particles", "x": 1040, "y": 310, "color": "#4169E1", "count": 100})

            # 音声
            wav_path = speak_voicevox(result, CHARACTERS["judge"]["speaker_id"])
            play_proc = subprocess.Popen(['afplay', wav_path],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            play_proc.wait()
            os.remove(wav_path)

        except Exception as e:
            self.message_queue.put({"action": "subtitle", "text": f"[判定エラー: {e}]"})

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    print("=" * 50)
    print("AI Debate YouTube Edition")
    print("=" * 50)
    print("\n⚠️  VOICEVOXを起動してから実行してください\n")

    app = YouTubeDebateApp()
    app.run()
