"""
Character Window - Tkinterを使用したキャラクター表示ウィンドウ
口パクアニメーション付きでAIの発言を視覚化
"""

import tkinter as tk
from tkinter import Canvas
from PIL import Image, ImageDraw, ImageTk
import os
import threading
import subprocess
import tempfile
import time


class CharacterWindow:
    """キャラクター表示用のTkinterウィンドウ"""

    def __init__(self, pro_name: str = "タケシ", con_name: str = "ユミ"):
        self.pro_name = pro_name
        self.con_name = con_name
        self.root = None
        self.canvas = None
        self.images = {}
        self.current_speaker = None
        self.is_speaking = False
        self.mouth_open = False
        self.animation_thread = None
        self.stop_animation = False

        # 画像のパス
        self.assets_dir = os.path.join(os.path.dirname(__file__), "assets")

        # 画像を事前生成
        self._ensure_assets()

    def _ensure_assets(self):
        """assetsフォルダと画像が存在することを確認"""
        if not os.path.exists(self.assets_dir):
            os.makedirs(self.assets_dir)

        # 必要な画像ファイル
        required_images = [
            "pro_closed.png", "pro_open.png",
            "con_closed.png", "con_open.png"
        ]

        # 画像がなければ生成
        for img_name in required_images:
            img_path = os.path.join(self.assets_dir, img_name)
            if not os.path.exists(img_path):
                self._generate_character_image(img_name)

    def _generate_character_image(self, filename: str):
        """Pillowでキャラクター画像を生成"""
        size = 200
        img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        # キャラクタータイプと口の状態を判定
        is_pro = filename.startswith("pro")
        is_open = "open" in filename

        # 色設定
        if is_pro:
            # タケシ: 青系
            face_color = (135, 206, 250)  # ライトスカイブルー
            hair_color = (50, 50, 80)     # ダークブルー
        else:
            # ユミ: 赤系
            face_color = (255, 182, 193)  # ライトピンク
            hair_color = (139, 69, 19)    # ブラウン

        # 髪（背景）
        if is_pro:
            # 短髪風（上部のみ）
            draw.ellipse([30, 10, 170, 100], fill=hair_color)
        else:
            # 長髪風（両サイドに伸びる）
            draw.ellipse([20, 10, 180, 120], fill=hair_color)
            draw.ellipse([10, 60, 60, 180], fill=hair_color)
            draw.ellipse([140, 60, 190, 180], fill=hair_color)

        # 顔
        draw.ellipse([40, 40, 160, 170], fill=face_color)

        # 目
        eye_y = 90
        draw.ellipse([65, eye_y, 85, eye_y + 25], fill=(255, 255, 255))
        draw.ellipse([115, eye_y, 135, eye_y + 25], fill=(255, 255, 255))
        # 瞳
        draw.ellipse([70, eye_y + 5, 82, eye_y + 20], fill=(50, 50, 50))
        draw.ellipse([120, eye_y + 5, 132, eye_y + 20], fill=(50, 50, 50))
        # ハイライト
        draw.ellipse([72, eye_y + 7, 77, eye_y + 12], fill=(255, 255, 255))
        draw.ellipse([122, eye_y + 7, 127, eye_y + 12], fill=(255, 255, 255))

        # 口
        mouth_y = 135
        if is_open:
            # 開いた口（楕円）
            draw.ellipse([85, mouth_y, 115, mouth_y + 20], fill=(200, 100, 100))
        else:
            # 閉じた口（線）
            draw.arc([85, mouth_y, 115, mouth_y + 15], start=0, end=180, fill=(150, 80, 80), width=2)

        # 保存
        img_path = os.path.join(self.assets_dir, filename)
        img.save(img_path)
        print(f"Generated: {img_path}")

    def start(self):
        """ウィンドウを別スレッドで起動"""
        self.window_thread = threading.Thread(target=self._run_window, daemon=True)
        self.window_thread.start()

    def _run_window(self):
        """Tkinterウィンドウを実行"""
        self.root = tk.Tk()
        self.root.title("AI Debate Characters")
        self.root.geometry("500x300")
        self.root.configure(bg='white')

        # 画像をロード
        self._load_images()

        # キャンバス作成
        self.canvas = Canvas(self.root, width=500, height=250, bg='white', highlightthickness=0)
        self.canvas.pack(pady=10)

        # 名前ラベル用フレーム
        name_frame = tk.Frame(self.root, bg='white')
        name_frame.pack()

        # 名前ラベル
        self.pro_label = tk.Label(name_frame, text=f"🟢 {self.pro_name}",
                                   font=("Helvetica", 14), bg='white', fg='green')
        self.pro_label.pack(side=tk.LEFT, padx=50)

        self.con_label = tk.Label(name_frame, text=f"🔴 {self.con_name}",
                                   font=("Helvetica", 14), bg='white', fg='red')
        self.con_label.pack(side=tk.RIGHT, padx=50)

        # 初期表示
        self._draw_characters()

        self.root.mainloop()

    def _load_images(self):
        """画像をロード"""
        image_files = {
            'pro_closed': 'pro_closed.png',
            'pro_open': 'pro_open.png',
            'con_closed': 'con_closed.png',
            'con_open': 'con_open.png',
        }

        for key, filename in image_files.items():
            path = os.path.join(self.assets_dir, filename)
            if os.path.exists(path):
                img = Image.open(path)
                img = img.resize((150, 150), Image.Resampling.LANCZOS)
                self.images[key] = ImageTk.PhotoImage(img)

    def _draw_characters(self):
        """キャラクターを描画"""
        if not self.canvas:
            return

        self.canvas.delete("all")

        # 賛成派（左側）
        pro_key = 'pro_open' if (self.current_speaker == 'pro' and self.mouth_open) else 'pro_closed'
        if pro_key in self.images:
            self.canvas.create_image(125, 125, image=self.images[pro_key])

        # 反対派（右側）
        con_key = 'con_open' if (self.current_speaker == 'con' and self.mouth_open) else 'con_closed'
        if con_key in self.images:
            self.canvas.create_image(375, 125, image=self.images[con_key])

        # 話者をハイライト
        if self.current_speaker == 'pro':
            self.canvas.create_oval(45, 45, 205, 205, outline='green', width=3)
        elif self.current_speaker == 'con':
            self.canvas.create_oval(295, 45, 455, 205, outline='red', width=3)

    def speak_with_animation(self, text: str, speaker: str, voice: str):
        """音声読み上げと口パクアニメーションを同時実行"""
        self.current_speaker = speaker
        self.is_speaking = True
        self.stop_animation = False

        # 音声ファイルを生成
        with tempfile.NamedTemporaryFile(suffix='.aiff', delete=False) as f:
            audio_path = f.name

        try:
            # 音声ファイル生成
            subprocess.run(['say', '-v', voice, '-r', '140', '-o', audio_path, text],
                          check=True, capture_output=True)

            # 音声ファイルの長さを取得（afinfo使用）
            result = subprocess.run(['afinfo', '-b', audio_path],
                                   capture_output=True, text=True)
            # 長さを推定（文字数ベース）
            duration = len(text) * 0.1 + 0.5  # 大まかな推定

            # 音声再生とアニメーションを開始
            play_thread = threading.Thread(target=lambda: subprocess.run(
                ['afplay', audio_path], capture_output=True))
            play_thread.start()

            # 口パクアニメーション
            start_time = time.time()
            while play_thread.is_alive() and not self.stop_animation:
                self.mouth_open = not self.mouth_open
                if self.root:
                    self.root.after(0, self._draw_characters)
                time.sleep(0.1)

            play_thread.join()

        finally:
            # クリーンアップ
            self.mouth_open = False
            self.is_speaking = False
            if self.root:
                self.root.after(0, self._draw_characters)

            # 一時ファイル削除
            if os.path.exists(audio_path):
                os.remove(audio_path)

    def stop(self):
        """アニメーションを停止"""
        self.stop_animation = True
        self.is_speaking = False

    def close(self):
        """ウィンドウを閉じる"""
        self.stop()
        if self.root:
            self.root.after(0, self.root.destroy)


# テスト用
if __name__ == "__main__":
    window = CharacterWindow()
    window.start()

    time.sleep(1)

    # テスト発話
    print("Testing pro character...")
    window.speak_with_animation("こんにちは、私はタケシです。", "pro", "Rocko (日本語（日本）)")

    time.sleep(0.5)

    print("Testing con character...")
    window.speak_with_animation("私はユミです。よろしく。", "con", "Kyoko")

    time.sleep(2)
    window.close()
