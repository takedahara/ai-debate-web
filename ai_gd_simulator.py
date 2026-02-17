"""
AI グループディスカッション シミュレーター
就活生向けGD練習・観戦アプリ

機能:
- 5人のAI就活生によるリアルなGD
- 役職: 司会、書記、タイムキーパー、アイデアマン、発表役
- 各キャラのレベル設定（専門性、コミュ力、論理力、協調性、発想力）
- 時間設定可能
- 評価AIによる順位付け
- 下剋上演出
"""

import tkinter as tk
from tkinter import Canvas, simpledialog, ttk
from PIL import Image, ImageDraw, ImageTk
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

# 役職定義
ROLES = ["司会", "書記", "タイムキーパー", "アイデアマン", "発表役"]

# デフォルトキャラクター設定
DEFAULT_CHARACTERS = [
    {
        "name": "ゆうき",
        "role": "司会",
        "gender": "male",
        "personality": "真面目で責任感が強い。緊張しやすいが、場をまとめようと頑張る",
        "speech_style": "丁寧語で話す。「えーと」「あの」が多い",
        "speaker_id": 3,  # ずんだもん
        "color": "#4169E1",
        "stats": {"専門性": 3, "コミュ力": 4, "論理力": 3, "協調性": 4, "発想力": 3},
    },
    {
        "name": "みさき",
        "role": "書記",
        "gender": "female",
        "personality": "几帳面でメモを取るのが得意。控えめだが鋭い意見を言う",
        "speech_style": "落ち着いた敬語。要点をまとめて話す",
        "speaker_id": 2,  # 四国めたん
        "color": "#FF69B4",
        "stats": {"専門性": 4, "コミュ力": 2, "論理力": 4, "協調性": 3, "発想力": 3},
    },
    {
        "name": "けんた",
        "role": "タイムキーパー",
        "gender": "male",
        "personality": "明るくムードメーカー。時間管理はしっかりするが、自分の意見も言いたい",
        "speech_style": "フランクな敬語。「〜っすね」など砕けた表現も",
        "speaker_id": 13,  # 剣崎雌雄
        "color": "#32CD32",
        "stats": {"専門性": 2, "コミュ力": 5, "論理力": 2, "協調性": 4, "発想力": 3},
    },
    {
        "name": "りこ",
        "role": "アイデアマン",
        "gender": "female",
        "personality": "発想力豊かで独創的。たまに突拍子もないことを言う",
        "speech_style": "少し早口。「〜だと思うんですけど」が口癖",
        "speaker_id": 14,  # 白上虎太郎
        "color": "#FFD700",
        "stats": {"専門性": 3, "コミュ力": 3, "論理力": 2, "協調性": 3, "発想力": 5},
    },
    {
        "name": "しょうた",
        "role": "発表役",
        "gender": "male",
        "personality": "堂々としていて発表が得意。少しプライドが高い",
        "speech_style": "はきはきとした敬語。自信を持って話す",
        "speaker_id": 8,  # 春日部つむぎ
        "color": "#9370DB",
        "stats": {"専門性": 4, "コミュ力": 4, "論理力": 4, "協調性": 2, "発想力": 2},
    },
]

# 評価AI
JUDGE_SPEAKER_ID = 47  # ナースロボ＿タイプＴ


def get_groq_response(prompt: str, system_prompt: str, max_tokens: int = 300) -> str:
    """Groq API"""
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)

    for attempt in range(5):  # リトライ回数を増やす
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
                wait_time = 10 * (attempt + 1)  # 待機時間を長く
                print(f"[DEBUG] Rate limit hit, waiting {wait_time}s (attempt {attempt + 1}/5)")
                time.sleep(wait_time)
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
    try:
        query = requests.post(
            f"{VOICEVOX_URL}/audio_query",
            params={"text": text, "speaker": speaker_id}, timeout=30
        ).json()
        query["speedScale"] = 1.0

        audio = requests.post(
            f"{VOICEVOX_URL}/synthesis",
            params={"speaker": speaker_id}, json=query, timeout=60
        ).content

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(audio)
            return f.name
    except Exception as e:
        print(f"VOICEVOX error: {e}")
        return None


def get_total_score(stats: dict) -> int:
    """総合スコアを計算"""
    return sum(stats.values())


class GDSimulatorApp:
    """グループディスカッション シミュレーター"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AI グループディスカッション シミュレーター")
        self.root.geometry("1400x800")
        self.root.configure(bg='#1a1a2e')

        # キャラクター設定（コピーして使う）
        self.characters = [dict(c) for c in DEFAULT_CHARACTERS]
        for c in self.characters:
            c["stats"] = dict(c["stats"])

        self.assets_dir = os.path.join(os.path.dirname(__file__), "assets_gd")
        self._ensure_assets()

        self.images = {}
        self.current_speaker_idx = None
        self.mouth_open = False
        self.is_running = False
        self.is_speaking = False
        self.topic = ""
        self.gd_time_minutes = 15
        self.discussion_log = []
        self.phase = ""
        self.start_time = None
        self.remaining_seconds = 0

        self.message_queue = queue.Queue()

        self._setup_ui()
        self._load_images()
        self._check_voicevox()

        self.root.after(16, self._process_queue)
        self.root.after(80, self._animate_mouth)
        self.root.after(1000, self._update_timer)

    def _ensure_assets(self):
        """画像アセット準備"""
        if not os.path.exists(self.assets_dir):
            os.makedirs(self.assets_dir)

        for i, char in enumerate(self.characters):
            for mouth in ["closed", "open"]:
                filename = f"char{i}_{mouth}.png"
                path = os.path.join(self.assets_dir, filename)
                if not os.path.exists(path):
                    self._generate_character_image(i, mouth == "open")

    def _generate_character_image(self, char_idx: int, is_open: bool):
        """キャラクター画像を生成"""
        size = 200
        img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        char = self.characters[char_idx]
        is_male = char["gender"] == "male"

        # 色をキャラごとに変える
        colors = [
            ((100, 149, 237), (50, 50, 100)),   # 青系
            ((255, 182, 193), (139, 69, 19)),    # ピンク系
            ((144, 238, 144), (34, 139, 34)),    # 緑系
            ((255, 215, 0), (184, 134, 11)),     # 黄系
            ((221, 160, 221), (128, 0, 128)),    # 紫系
        ]
        face_color, hair_color = colors[char_idx % len(colors)]

        # 髪
        if is_male:
            draw.ellipse([30, 10, 170, 90], fill=hair_color)
        else:
            draw.ellipse([20, 5, 180, 100], fill=hair_color)
            draw.ellipse([10, 50, 50, 180], fill=hair_color)
            draw.ellipse([150, 50, 190, 180], fill=hair_color)

        # 顔
        draw.ellipse([40, 40, 160, 170], fill=(255, 228, 196))

        # 目
        eye_y = 85
        draw.ellipse([60, eye_y, 85, eye_y + 30], fill=(255, 255, 255))
        draw.ellipse([115, eye_y, 140, eye_y + 30], fill=(255, 255, 255))
        draw.ellipse([65, eye_y + 8, 80, eye_y + 25], fill=(50, 50, 50))
        draw.ellipse([120, eye_y + 8, 135, eye_y + 25], fill=(50, 50, 50))

        # 口
        mouth_y = 135
        if is_open:
            draw.ellipse([85, mouth_y, 115, mouth_y + 18], fill=(200, 100, 100))
        else:
            draw.arc([85, mouth_y, 115, mouth_y + 12], start=0, end=180, fill=(150, 80, 80), width=2)

        # スーツ（就活生らしく）
        draw.polygon([(60, 165), (100, 200), (140, 165)], fill=(30, 30, 30))
        draw.polygon([(70, 170), (100, 195), (130, 170)], fill=(255, 255, 255))

        mouth_state = "open" if is_open else "closed"
        img.save(os.path.join(self.assets_dir, f"char{char_idx}_{mouth_state}.png"))

    def _load_images(self):
        """画像をロード"""
        max_size = 150
        for i in range(len(self.characters)):
            for mouth in ["closed", "open"]:
                key = f"char{i}_{mouth}"
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
        # 左側：キャラクター表示エリア
        left_frame = tk.Frame(self.root, bg='#1a1a2e')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=10, pady=10)

        # タイトル
        tk.Label(left_frame, text="👔 GDシミュレーター", font=("Helvetica", 20, "bold"),
                bg='#1a1a2e', fg='white').pack(pady=5)

        # ステータス
        self.status_label = tk.Label(left_frame, text="確認中...", font=("Helvetica", 10),
                                     bg='#1a1a2e', fg='gray')
        self.status_label.pack()

        # タイマー表示
        timer_frame = tk.Frame(left_frame, bg='#1a1a2e')
        timer_frame.pack(pady=5)

        self.timer_label = tk.Label(timer_frame, text="⏱ --:--", font=("Helvetica", 24, "bold"),
                                    bg='#1a1a2e', fg='#00FF00')
        self.timer_label.pack(side=tk.LEFT, padx=10)

        # フェーズ表示
        self.phase_label = tk.Label(timer_frame, text="", font=("Helvetica", 14, "bold"),
                                    bg='#1a1a2e', fg='#FFD700')
        self.phase_label.pack(side=tk.LEFT, padx=10)

        # キャラクターキャンバス
        self.char_canvas = Canvas(left_frame, width=800, height=400, bg='#2d2d5a', highlightthickness=0)
        self.char_canvas.pack(pady=10)

        # 議題表示
        self.topic_label = tk.Label(left_frame, text="", font=("Helvetica", 14),
                                    bg='#1a1a2e', fg='#00d4ff', wraplength=700)
        self.topic_label.pack(pady=5)

        # 字幕
        self.subtitle_frame = tk.Frame(left_frame, bg='#000000')
        self.subtitle_frame.pack(fill=tk.X, pady=5)
        self.subtitle_label = tk.Label(self.subtitle_frame, text="", font=("Helvetica", 14),
                                       bg='#000000', fg='white', wraplength=750, justify=tk.LEFT)
        self.subtitle_label.pack(pady=10, padx=10)

        # 右側：設定パネル
        right_frame = tk.Frame(self.root, bg='#16213e', width=350)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)
        right_frame.pack_propagate(False)

        tk.Label(right_frame, text="⚙️ 設定", font=("Helvetica", 16, "bold"),
                bg='#16213e', fg='white').pack(pady=10)

        # 時間設定
        time_frame = tk.Frame(right_frame, bg='#16213e')
        time_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(time_frame, text="GD時間（分）:", font=("Helvetica", 12),
                bg='#16213e', fg='white').pack(side=tk.LEFT)
        self.time_var = tk.StringVar(value="15")
        time_entry = tk.Entry(time_frame, textvariable=self.time_var, width=5, font=("Helvetica", 12))
        time_entry.pack(side=tk.LEFT, padx=5)

        # キャラクター設定
        tk.Label(right_frame, text="📊 キャラクターレベル", font=("Helvetica", 14, "bold"),
                bg='#16213e', fg='white').pack(pady=10)

        self.stat_vars = []
        stats_frame = tk.Frame(right_frame, bg='#16213e')
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=5)

        # スクロール可能なキャンバス
        canvas = Canvas(stats_frame, bg='#16213e', highlightthickness=0)
        scrollbar = tk.Scrollbar(stats_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#16213e')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for i, char in enumerate(self.characters):
            char_frame = tk.Frame(scrollable_frame, bg='#1a1a2e', relief=tk.RAISED, bd=1)
            char_frame.pack(fill=tk.X, pady=3, padx=3)

            header = tk.Frame(char_frame, bg=char["color"])
            header.pack(fill=tk.X)
            tk.Label(header, text=f"{char['name']}（{char['role']}）",
                    font=("Helvetica", 11, "bold"), bg=char["color"], fg='white').pack(pady=2)

            stat_dict = {}
            for stat_name in ["専門性", "コミュ力", "論理力", "協調性", "発想力"]:
                stat_frame = tk.Frame(char_frame, bg='#1a1a2e')
                stat_frame.pack(fill=tk.X, padx=5)
                tk.Label(stat_frame, text=f"{stat_name}:", font=("Helvetica", 9),
                        bg='#1a1a2e', fg='white', width=8, anchor='w').pack(side=tk.LEFT)

                var = tk.IntVar(value=char["stats"][stat_name])
                stat_dict[stat_name] = var

                for val in range(1, 6):
                    rb = tk.Radiobutton(stat_frame, text=str(val), variable=var, value=val,
                                       bg='#1a1a2e', fg='white', selectcolor='#4a4a6a',
                                       font=("Helvetica", 9))
                    rb.pack(side=tk.LEFT)

            self.stat_vars.append(stat_dict)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ボタン
        btn_frame = tk.Frame(right_frame, bg='#16213e')
        btn_frame.pack(pady=10)

        self.start_btn = tk.Button(btn_frame, text="▶ GD開始", font=("Helvetica", 12),
                                   command=self._start_gd, width=12)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = tk.Button(btn_frame, text="⏹ 終了", font=("Helvetica", 12),
                                  command=self._stop_gd, state=tk.DISABLED, width=12)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self._draw_characters()

    def _draw_characters(self):
        """キャラクター描画"""
        self.char_canvas.delete("all")

        # 5人を配置
        positions = [
            (80, 200), (240, 100), (400, 200), (560, 100), (720, 200)
        ]

        for i, (x, y) in enumerate(positions):
            char = self.characters[i]

            # 背景円
            is_speaking = (self.current_speaker_idx == i)
            outline_color = '#FFFF00' if is_speaking else char["color"]
            outline_width = 4 if is_speaking else 2
            self.char_canvas.create_oval(x-70, y-70, x+70, y+70,
                                         outline=outline_color, width=outline_width, fill='#3d3d6a')

            # キャラ画像
            mouth = "open" if (is_speaking and self.mouth_open) else "closed"
            key = f"char{i}_{mouth}"
            if key in self.images:
                self.char_canvas.create_image(x, y, image=self.images[key])

            # 名前と役職
            self.char_canvas.create_text(x, y + 85, text=char["name"],
                                        font=("Helvetica", 12, "bold"), fill='white')
            self.char_canvas.create_text(x, y + 102, text=f"[{char['role']}]",
                                        font=("Helvetica", 10), fill=char["color"])

            # 総合スコア表示
            total = get_total_score(char["stats"])
            self.char_canvas.create_text(x, y + 118, text=f"総合:{total}",
                                        font=("Helvetica", 9), fill='#aaaaaa')

    def _animate_mouth(self):
        """口パクアニメーション"""
        if self.is_speaking:
            self.mouth_open = not self.mouth_open
            self._draw_characters()
        self.root.after(80, self._animate_mouth)

    def _update_timer(self):
        """タイマー更新"""
        if self.is_running and self.start_time:
            elapsed = time.time() - self.start_time
            self.remaining_seconds = max(0, self.gd_time_minutes * 60 - elapsed)
            mins = int(self.remaining_seconds // 60)
            secs = int(self.remaining_seconds % 60)

            # 残り時間による色変更
            if self.remaining_seconds <= 60:
                color = '#FF0000'  # 赤
            elif self.remaining_seconds <= 180:
                color = '#FFA500'  # オレンジ
            else:
                color = '#00FF00'  # 緑

            self.timer_label.config(text=f"⏱ {mins:02d}:{secs:02d}", fg=color)
        self.root.after(1000, self._update_timer)

    def _get_remaining_time_str(self) -> str:
        """残り時間の文字列を取得"""
        mins = int(self.remaining_seconds // 60)
        if mins > 1:
            return f"残り{mins}分"
        else:
            return "残り1分程度"

    def _process_queue(self):
        """メッセージキュー処理"""
        try:
            while True:
                msg = self.message_queue.get_nowait()
                action = msg.get("action")

                if action == "speaker":
                    self.current_speaker_idx = msg["idx"]
                    self._draw_characters()
                elif action == "speaking":
                    self.is_speaking = msg["value"]
                    if not self.is_speaking:
                        self.mouth_open = False
                        self._draw_characters()
                elif action == "subtitle":
                    speaker_name = msg.get("speaker", "")
                    text = msg.get("text", "")
                    if speaker_name:
                        self.subtitle_label.config(text=f"【{speaker_name}】{text}")
                    else:
                        self.subtitle_label.config(text=text)
                elif action == "phase":
                    self.phase = msg["value"]
                    self.phase_label.config(text=f"📍 {self.phase}")
                elif action == "done":
                    self.is_running = False
                    self.is_speaking = False
                    self.start_btn.config(state=tk.NORMAL)
                    self.stop_btn.config(state=tk.DISABLED)
                    self.current_speaker_idx = None
                    self._draw_characters()

        except queue.Empty:
            pass

        self.root.after(16, self._process_queue)

    def _apply_stat_settings(self):
        """設定を適用"""
        for i, stat_dict in enumerate(self.stat_vars):
            for stat_name, var in stat_dict.items():
                self.characters[i]["stats"][stat_name] = var.get()

    def _start_gd(self):
        """GD開始"""
        if not self.voicevox_available:
            self._check_voicevox()
            if not self.voicevox_available:
                return

        topic = simpledialog.askstring("お題", "GDのお題を入力してください:",
                                       initialvalue="コンビニの売上を2倍にする方法を考えてください")
        if not topic:
            return

        try:
            self.gd_time_minutes = int(self.time_var.get())
        except:
            self.gd_time_minutes = 15

        self._apply_stat_settings()
        self.topic = topic
        self.discussion_log = []
        self.topic_label.config(text=f"📋 お題: {topic}")

        self.is_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        self._draw_characters()

        thread = threading.Thread(target=self._gd_loop, daemon=True)
        thread.start()

    def _stop_gd(self):
        self.is_running = False
        self.stop_btn.config(state=tk.DISABLED)

    def _create_character_prompt(self, char: dict) -> str:
        """キャラクター用システムプロンプト"""
        stats = char["stats"]
        level_desc = []
        for stat, val in stats.items():
            if val >= 4:
                level_desc.append(f"{stat}が高い")
            elif val <= 2:
                level_desc.append(f"{stat}が低め")

        return f"""あなたは就活中の大学生「{char['name']}」です。グループディスカッションに参加しています。

【あなたの役職】{char['role']}

【性格】{char['personality']}

【話し方】{char['speech_style']}

【能力特性】{', '.join(level_desc) if level_desc else '平均的な能力'}

【重要なルール】
- 就活生らしく敬語で話す
- 1〜2文で話す
- 自分の新しい視点やアイデアを言う
- 具体的な例や数字を入れると良い
- 「えーと」「あの」など自然な言葉を入れる
- 基本的に直接自分の意見を言う（「〜を踏まえて」「皆さんの意見を〜」は毎回使わない）"""

    def _create_discuss_prompt(self, round_num: int) -> str:
        """議論プロンプトを生成（簡潔版）"""
        if round_num == 0:
            return f"「{self.topic}」について意見を1文で。"
        else:
            # 直前の2発言だけ
            recent = self.discussion_log[-2:] if len(self.discussion_log) >= 2 else self.discussion_log
            recent_text = " / ".join([f"{d['speaker']}:{d['text'][:30]}" for d in recent])
            return f"お題:{self.topic}\n直前:{recent_text}\n→あなたの意見を1文で。"

    def _speak(self, char_idx: int, text: str, wav_path: str = None):
        """発言処理（wav_pathが渡されれば音声生成をスキップ）"""
        char = self.characters[char_idx]
        self.discussion_log.append({"speaker": char["name"], "role": char["role"], "text": text})
        self.last_speaker_idx = char_idx

        self.message_queue.put({"action": "speaker", "idx": char_idx})
        self.message_queue.put({"action": "subtitle", "speaker": char["name"], "text": text})

        # 音声生成（先読みされていなければ）
        if wav_path is None:
            wav_path = speak_voicevox(text, char["speaker_id"])

        if wav_path:
            self.message_queue.put({"action": "speaking", "value": True})
            try:
                proc = subprocess.Popen(['afplay', wav_path],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                proc.wait()
            finally:
                self.message_queue.put({"action": "speaking", "value": False})
                if os.path.exists(wav_path):
                    os.remove(wav_path)

    def _gd_loop(self):
        """GDメインループ"""
        facilitator_idx = 0  # 司会
        timekeeper_idx = 2   # タイムキーパー
        self.last_speaker_idx = -1  # 前回の発言者（連続防止用）

        # タイマー開始
        self.start_time = time.time()

        # === 時間配分決定 ===
        self.message_queue.put({"action": "phase", "value": "時間配分"})

        # 司会が時間配分を提案
        self._speak(facilitator_idx, f"えーと、{self.gd_time_minutes}分なので、議論{self.gd_time_minutes - 5}分、まとめ5分でいきましょう。")

        # 同意
        self._speak(timekeeper_idx, "了解です、時間見ておきます。")

        if not self.is_running:
            self.message_queue.put({"action": "done"})
            return

        # === 前提確認（必要に応じて）===
        self.message_queue.put({"action": "phase", "value": "前提確認"})
        time.sleep(2)  # レート制限対策

        # 前提確認が必要か判断
        premise_check_prompt = f"""お題「{self.topic}」について、前提確認は必要ですか？
必要な場合は確認すべき点を1つ質問してください。
不要な場合は「では早速議論に入りましょう」と言ってください。"""

        system = self._create_character_prompt(self.characters[facilitator_idx])
        response = get_groq_response(premise_check_prompt, system, max_tokens=100)
        self._speak(facilitator_idx, response.strip())

        # 誰かが答える
        if "議論" not in response and ("?" in response or "？" in response):
            time.sleep(2)  # レート制限対策
            answer_idx = random.choice([1, 3, 4])
            answer_prompt = f"""司会の質問「{response}」に対して、あなたの意見を1〜2文で答えてください。"""
            system = self._create_character_prompt(self.characters[answer_idx])
            answer = get_groq_response(answer_prompt, system, max_tokens=100)
            self._speak(answer_idx, answer.strip())

        if not self.is_running:
            self.message_queue.put({"action": "done"})
            return

        # === 議論 ===
        self.message_queue.put({"action": "phase", "value": "議論"})

        from concurrent.futures import ThreadPoolExecutor, Future

        round_num = 0
        executor = ThreadPoolExecutor(max_workers=3)

        # 次の発言者の準備用
        next_text_future: Future = None
        next_wav_future: Future = None
        next_speaker_idx = None

        while self.is_running:
            # 残り時間チェック
            elapsed = time.time() - self.start_time
            remaining = self.gd_time_minutes * 60 - elapsed
            print(f"[DEBUG] Round {round_num}, remaining: {remaining:.0f}s")

            # 残り10%でまとめに移行
            if remaining < self.gd_time_minutes * 60 * 0.10:
                # タイムキーパーがアナウンス
                msg = f"あ、{self._get_remaining_time_str()}です、まとめに入りましょう。"
                wav = speak_voicevox(msg, self.characters[timekeeper_idx]["speaker_id"])
                self._speak(timekeeper_idx, msg, wav)
                break

            # 発言者を決定
            speaker_idx = round_num % 5
            if speaker_idx == self.last_speaker_idx:
                speaker_idx = (speaker_idx + 1) % 5

            # 先読み結果があれば使う
            try:
                if next_text_future and next_speaker_idx == speaker_idx:
                    response = next_text_future.result(timeout=30)
                    wav_path = next_wav_future.result(timeout=60)
                else:
                    # 初回または先読みが使えない場合
                    discuss_prompt = self._create_discuss_prompt(round_num)
                    system = self._create_character_prompt(self.characters[speaker_idx])
                    response = get_groq_response(discuss_prompt, system, max_tokens=150).strip()
                    wav_path = speak_voicevox(response, self.characters[speaker_idx]["speaker_id"])
            except Exception as e:
                print(f"[DEBUG] Error in round {round_num}: {e}")
                # エラー時は新規生成を試みる
                discuss_prompt = self._create_discuss_prompt(round_num)
                system = self._create_character_prompt(self.characters[speaker_idx])
                response = get_groq_response(discuss_prompt, system, max_tokens=150).strip()
                wav_path = speak_voicevox(response, self.characters[speaker_idx]["speaker_id"])

            # ログに追加
            speaker_name = self.characters[speaker_idx]["name"]
            self.discussion_log.append({
                "speaker": speaker_name,
                "role": self.characters[speaker_idx]["role"],
                "text": response
            })
            self.last_speaker_idx = speaker_idx

            # 次の発言者を決定
            next_speaker_idx = (speaker_idx + 1) % 5
            if next_speaker_idx == self.last_speaker_idx:
                next_speaker_idx = (next_speaker_idx + 1) % 5

            # テキスト生成が終わった瞬間に次のテキスト生成を開始
            try:
                next_prompt = self._create_discuss_prompt(round_num + 1)
                next_system = self._create_character_prompt(self.characters[next_speaker_idx])
                next_text_future = executor.submit(
                    lambda p=next_prompt, s=next_system: get_groq_response(p, s, max_tokens=150).strip()
                )

                # 音声生成も並列で開始（テキスト生成完了後）
                def generate_next_wav(text_future, spk_id):
                    try:
                        text = text_future.result(timeout=30)
                        return speak_voicevox(text, spk_id)
                    except Exception as e:
                        print(f"[DEBUG] Prefetch wav error: {e}")
                        return None

                next_wav_future = executor.submit(
                    generate_next_wav, next_text_future, self.characters[next_speaker_idx]["speaker_id"]
                )
            except Exception as e:
                print(f"[DEBUG] Prefetch submit error: {e}")
                next_text_future = None
                next_wav_future = None

            # 現在の発言を再生（この間に次の準備が進む）
            self.message_queue.put({"action": "speaker", "idx": speaker_idx})
            self.message_queue.put({"action": "subtitle", "speaker": speaker_name, "text": response})

            if wav_path:
                self.message_queue.put({"action": "speaking", "value": True})
                try:
                    proc = subprocess.Popen(['afplay', wav_path],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    proc.wait()
                finally:
                    self.message_queue.put({"action": "speaking", "value": False})
                    if os.path.exists(wav_path):
                        os.remove(wav_path)

            round_num += 1

        executor.shutdown(wait=False)

        if not self.is_running:
            self.message_queue.put({"action": "done"})
            return

        # === フェーズ5: まとめ ===
        self.message_queue.put({"action": "phase", "value": "まとめ"})

        # 書記がまとめる
        scribe_idx = 1
        # 最後の5発言だけ使う
        recent_discussion = self.discussion_log[-5:] if len(self.discussion_log) > 5 else self.discussion_log
        discussion_summary = "\n".join([f"{d['speaker']}: {d['text']}" for d in recent_discussion])

        summary_prompt = f"""お題: {self.topic}

これまでの議論:
{discussion_summary}

書記として、議論の要点を2〜3文でまとめてください。"""

        system = self._create_character_prompt(self.characters[scribe_idx])
        summary = get_groq_response(summary_prompt, system, max_tokens=200)
        self._speak(scribe_idx, summary.strip())

        if not self.is_running:
            self.message_queue.put({"action": "done"})
            return

        # === フェーズ6: 発表 ===
        self.message_queue.put({"action": "phase", "value": "発表"})
        time.sleep(0.3)

        presenter_idx = 4  # 発表役
        present_prompt = f"""お題: {self.topic}

議論のまとめ: {summary}

発表役として、「私たちのグループでは〜」から始めて、結論を2〜3文で発表してください。"""

        system = self._create_character_prompt(self.characters[presenter_idx])
        presentation = get_groq_response(present_prompt, system, max_tokens=200)
        self._speak(presenter_idx, presentation.strip())

        # === フェーズ7: 評価 ===
        self.message_queue.put({"action": "phase", "value": "評価発表"})
        time.sleep(1)

        self._run_evaluation()

        self.message_queue.put({"action": "done"})

    def _run_evaluation(self):
        """評価AIによる順位付け"""
        all_discussion = "\n".join([f"{d['speaker']}({d['role']}): {d['text']}" for d in self.discussion_log])

        # 各キャラの総合スコア
        scores_info = "\n".join([
            f"- {c['name']}({c['role']}): 総合スコア{get_total_score(c['stats'])}点"
            for c in self.characters
        ])

        eval_prompt = f"""以下のグループディスカッションを評価し、参加者5人の順位をつけてください。

【お題】{self.topic}

【参加者の事前スコア】
{scores_info}

【議論内容】
{all_discussion}

【評価基準】
- 議論への貢献度
- 発言の質
- 協調性
- 役職遂行度

以下の形式で回答してください：
🏆 1位: [名前] - [理由を1文で]
🥈 2位: [名前] - [理由を1文で]
🥉 3位: [名前] - [理由を1文で]
4位: [名前] - [理由を1文で]
5位: [名前] - [理由を1文で]

※事前スコアが低いのに上位なら「下剋上！」と付けてください。"""

        eval_system = "あなたはグループディスカッションの評価者です。公平に参加者を評価し、順位をつけてください。"

        result = get_groq_response(eval_prompt, eval_system, max_tokens=500)

        self.message_queue.put({"action": "subtitle", "speaker": "評価AI", "text": result})

        # 音声で発表
        wav_path = speak_voicevox(result, JUDGE_SPEAKER_ID)
        if wav_path:
            try:
                proc = subprocess.Popen(['afplay', wav_path],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                proc.wait()
            finally:
                if os.path.exists(wav_path):
                    os.remove(wav_path)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    print("=" * 50)
    print("AI グループディスカッション シミュレーター")
    print("=" * 50)
    print("\n⚠️  VOICEVOXを起動してから実行してください\n")

    app = GDSimulatorApp()
    app.run()
