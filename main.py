
import queue
import threading
import time
import tkinter as tk

import cv2
import customtkinter as ctk
import mediapipe as mp
from PIL import Image
from PIL import ImageTk


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class AirControlApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AirControl | Gesture + Voice Assistant")
        self.geometry("1100x720")
        self.minsize(900, 600)

        self.running = True
        self.camera_enabled = True
        self.frame_queue = queue.Queue(maxsize=1)
        self.status_queue = queue.Queue()

        self.status_var = tk.StringVar(value="Starting camera...")
        self.hand_var = tk.StringVar(value="Hands detected: 0")
        self.mode_var = tk.StringVar(value="Voice mode: Not connected")
        self.paused = False

        self._build_ui()

        self.camera_thread = threading.Thread(
            target=self._camera_worker,
            daemon=True,
        )
        self.camera_thread.start()

        self.after(20, self._update_dashboard)
        self.protocol("WM_DELETE_WINDOW", self._close_app)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, corner_radius=12)
        header.grid(
            row=0, column=0, padx=16, pady=(16, 8), sticky="ew"
        )

        ctk.CTkLabel(
            header,
            text="AIRCONTROL",
            font=ctk.CTkFont(size=28, weight="bold"),
        ).pack(side="left", padx=20, pady=16)

        self.pause_button = ctk.CTkButton(
            header,
            text="Pause",
            command=self._toggle_pause,
        )
        self.pause_button.pack(side="right", padx=16, pady=16)

        content = ctk.CTkFrame(self, corner_radius=12)
        content.grid(
            row=1, column=0, padx=16, pady=8, sticky="nsew"
        )
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        self.video_label = ctk.CTkLabel(
            content,
            text="Waiting for webcam...",
        )
        self.video_label.grid(
            row=0, column=0, padx=12, pady=12, sticky="nsew"
        )

        panel = ctk.CTkFrame(content)
        panel.grid(
            row=0, column=1, padx=(0, 12), pady=12, sticky="nsew"
        )

        ctk.CTkLabel(
            panel,
            text="SYSTEM STATUS",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(padx=12, pady=(18, 12))

        ctk.CTkLabel(
            panel, textvariable=self.status_var, wraplength=200
        ).pack(padx=12, pady=8)

        ctk.CTkLabel(
            panel, textvariable=self.hand_var, wraplength=200
        ).pack(padx=12, pady=8)

        ctk.CTkLabel(
            panel, textvariable=self.mode_var, wraplength=200
        ).pack(padx=12, pady=8)

        ctk.CTkLabel(
            panel,
            text="Next: cursor + gesture actions",
            wraplength=200,
        ).pack(padx=12, pady=(20, 8))

        footer = ctk.CTkLabel(
            self,
            text="Prototype • Camera processing runs separately",
        )
        footer.grid(row=2, column=0, padx=16, pady=(4, 12))

    def _camera_worker(self):
        mp_hands = mp.solutions.hands
        mp_draw = mp.solutions.drawing_utils

        cap = cv2.VideoCapture(0, cv2.CAP_MSMF)

        if not cap.isOpened():
            self.status_queue.put("ERROR: Cannot open webcam")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        try:
            with mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.6,
                min_tracking_confidence=0.6,
            ) as hands:

                self.status_queue.put("Camera connected")

                while self.running:
                    ok, frame = cap.read()

                    if not ok:
                        self.status_queue.put("Camera frame unavailable")
                        time.sleep(0.1)
                        continue

                    frame = cv2.flip(frame, 1)

                    if not self.paused:
                        rgb = cv2.cvtColor(
                            frame, cv2.COLOR_BGR2RGB
                        )
                        results = hands.process(rgb)

                        count = (
                            len(results.multi_hand_landmarks)
                            if results.multi_hand_landmarks
                            else 0
                        )

                        if results.multi_hand_landmarks:
                            for landmarks in results.multi_hand_landmarks:
                                mp_draw.draw_landmarks(
                                    frame,
                                    landmarks,
                                    mp_hands.HAND_CONNECTIONS,
                                )

                        self.status_queue.put(
                            f"Tracking active | {count} hand(s)"
                        )
                        self.status_queue.put(
                            f"HANDS:{count}"
                        )

                    rgb_frame = cv2.cvtColor(
                        frame, cv2.COLOR_BGR2RGB
                    )

                    # Keep only the newest frame so the UI doesn't lag.
                    try:
                        self.frame_queue.put_nowait(rgb_frame)
                    except queue.Full:
                        try:
                            self.frame_queue.get_nowait()
                        except queue.Empty:
                            pass

                        try:
                            self.frame_queue.put_nowait(rgb_frame)
                        except queue.Full:
                            pass

        finally:
            cap.release()

    def _update_dashboard(self):
        if not self.running:
            return

        while True:
            try:
                status = self.status_queue.get_nowait()
            except queue.Empty:
                break

            if status.startswith("HANDS:"):
                self.hand_var.set(
                    "Hands detected: " + status.split(":")[1]
                )
            else:
                self.status_var.set(status)

        try:
            frame = self.frame_queue.get_nowait()
            image = Image.fromarray(frame)

            width = max(self.video_label.winfo_width(), 400)
            height = max(self.video_label.winfo_height(), 300)
            image.thumbnail((width, height))

            photo = ImageTk.PhotoImage(image)
            self.video_label.configure(image=photo, text="")
            self.video_label.image = photo

        except queue.Empty:
            pass

        self.after(20, self._update_dashboard)

    def _toggle_pause(self):
        self.paused = not self.paused
        self.pause_button.configure(
            text="Resume" if self.paused else "Pause"
        )
        self.status_var.set(
            "Tracking paused" if self.paused else "Tracking resumed"
        )

    def _close_app(self):
        self.running = False
        self.destroy()


if __name__ == "__main__":
    app = AirControlApp()
    app.mainloop()
