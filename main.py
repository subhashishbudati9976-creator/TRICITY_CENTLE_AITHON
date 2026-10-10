import math
import queue
import string
import threading
import time
import tkinter as tk
import traceback

import cv2
import customtkinter as ctk
import mediapipe as mp
import pyautogui
from PIL import Image, ImageTk

from voice.voice_controller import VoiceController

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Keep PyAutoGUI's emergency corner fail-safe enabled.
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.01

SCREEN_W, SCREEN_H = pyautogui.size()


class AirControlApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AirControl | Gesture + Voice Assistant")
        self.geometry("1100x720")
        self.minsize(900, 600)

        # Shared state and queues MUST exist before any worker starts.
        self.running = True
        self.paused = True
        self.frame_queue = queue.Queue(maxsize=1)
        self.control_queue = queue.Queue(maxsize=1)
        self.status_queue = queue.Queue()
        self.command_queue = queue.Queue()
        self.voice_controller = VoiceController()
        self.voice_mode = "online"
        self.voice_busy = False

        self.status_var = tk.StringVar(master=self, value="Camera starting...")
        self.hand_var = tk.StringVar(master=self, value="Hands detected: 0")
        self.control_var = tk.StringVar(master=self, value="Mouse control: DISABLED")
        self.voice_status_var = tk.StringVar(master=self, value="Voice: Ready")

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._close_app)

        self.camera_thread = threading.Thread(target=self._camera_worker, daemon=True)
        self.mouse_thread = threading.Thread(target=self._mouse_worker, daemon=True)
        self.camera_thread.start()
        self.mouse_thread.start()

        self.after(20, self._update_dashboard)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, corner_radius=12)
        header.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="ew")
        ctk.CTkLabel(header, text="AIRCONTROL", font=ctk.CTkFont(size=28, weight="bold")).pack(side="left", padx=20, pady=16)
        self.pause_button = ctk.CTkButton(header, text="Enable Mouse Control", command=self._toggle_pause)
        self.pause_button.pack(side="right", padx=16, pady=16)

        content = ctk.CTkFrame(self, corner_radius=12)
        content.grid(row=1, column=0, padx=16, pady=8, sticky="nsew")
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        self.video_label = ctk.CTkLabel(content, text="Waiting for webcam...")
        self.video_label.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")

        panel = ctk.CTkFrame(content)
        panel.grid(row=0, column=1, padx=(0, 12), pady=12, sticky="nsew")
        ctk.CTkLabel(panel, text="SYSTEM STATUS", font=ctk.CTkFont(size=18, weight="bold")).pack(padx=12, pady=(18, 12))

        for variable in (self.status_var, self.hand_var, self.control_var):
            ctk.CTkLabel(panel, textvariable=variable, wraplength=210).pack(padx=12, pady=10)

        ctk.CTkLabel(
            panel,
            text="Move index finger to move cursor.\n\nPinch thumb + index finger to click.\n\nClick Enable before testing.",
            justify="left", wraplength=210,
        ).pack(padx=12, pady=18)

        ctk.CTkLabel(
            self,
            text="Safety: press Pause to disable control. Move mouse to the top-left corner for PyAutoGUI's emergency fail-safe.",
            wraplength=900,
        ).grid(row=2, column=0, padx=16, pady=(4, 12))

        ctk.CTkLabel(panel, text="VOICE CONTROL", font=ctk.CTkFont(size=16, weight="bold")).pack(padx=12, pady=(20, 8))
        self.voice_mode_button = ctk.CTkSegmentedButton(panel, values=["Online", "Offline"], command=self._set_voice_mode)
        self.voice_mode_button.set("Online")
        self.voice_mode_button.pack(padx=12, pady=8)
        ctk.CTkLabel(panel, textvariable=self.voice_status_var, wraplength=210).pack(padx=12, pady=8)
        self.listen_button = ctk.CTkButton(panel, text="Listen for Command", command=self._start_voice)
        self.listen_button.pack(padx=12, pady=8)

    def _publish_control(self, command):
        """Keep only the newest gesture sample."""
        try:
            self.control_queue.put_nowait(command)
        except queue.Full:
            try:
                self.control_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self.control_queue.put_nowait(command)
            except queue.Full:
                pass

    def _camera_worker(self):
        hands_module = mp.solutions.hands
        drawing = mp.solutions.drawing_utils
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            self.status_queue.put("ERROR: Webcam unavailable")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        try:
            with hands_module.Hands(
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
                        time.sleep(0.05)
                        continue

                    frame = cv2.flip(frame, 1)
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    result = hands.process(rgb)
                    detected_hands = result.multi_hand_landmarks or []

                    for hand_landmarks in detected_hands:
                        drawing.draw_landmarks(frame, hand_landmarks, hands_module.HAND_CONNECTIONS)

                    if detected_hands:
                        # The first detected hand controls the cursor; both hands are displayed.
                        landmarks = detected_hands[0]
                        index_tip = landmarks.landmark[8]
                        thumb_tip = landmarks.landmark[4]
                        wrist = landmarks.landmark[0]
                        middle_mcp = landmarks.landmark[9]

                        pinch_distance = math.hypot(index_tip.x - thumb_tip.x, index_tip.y - thumb_tip.y)
                        palm_size = math.hypot(middle_mcp.x - wrist.x, middle_mcp.y - wrist.y)
                        pinch_ratio = pinch_distance / palm_size if palm_size > 0.001 else 1.0
                        pinching = pinch_ratio < 0.32

                        cv2.putText(
                            frame, "PINCH" if pinching else "OPEN", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1,
                            (0, 255, 0) if pinching else (255, 255, 255), 2,
                        )
                        self._publish_control((index_tip.x, index_tip.y, pinching))
                    else:
                        self._publish_control((None, None, False))

                    self.status_queue.put(f"HANDS:{len(detected_hands)}")
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
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
        except Exception as exc:
            self.status_queue.put(f"Camera error: {exc}")
            traceback.print_exc()
        finally:
            cap.release()

    def _mouse_worker(self):
        smooth_x = smooth_y = None
        previous_pinch = False
        last_click_time = 0.0
        smoothing = 0.30
        click_cooldown = 0.45

        while self.running:
            try:
                # 1. Drain all pending voice commands first so they execute immediately
                # regardless of gesture tracking pause state or camera status.
                while True:
                    try:
                        command = self.command_queue.get_nowait()
                    except queue.Empty:
                        break

                    if command:
                        try:
                            self._execute_voice_command(command)
                        except pyautogui.FailSafeException:
                            self.paused = True
                            self.status_queue.put("CONTROL:PAUSED")
                            self.status_queue.put("Safety stop: mouse control disabled")
                        except Exception as exc:
                            self.status_queue.put(f"Command error: {exc}")
                            traceback.print_exc()

                # 2. Get next gesture sample (timeout 0.02s keeps loop responsive)
                try:
                    x, y, pinching = self.control_queue.get(timeout=0.02)
                except queue.Empty:
                    continue

                if self.paused or x is None or y is None:
                    previous_pinch = False
                    smooth_x = smooth_y = None
                    continue

                x = max(0.08, min(0.92, x))
                y = max(0.08, min(0.92, y))
                margin = 20
                target_x = margin + ((x - 0.08) / 0.84) * (SCREEN_W - 2 * margin)
                target_y = margin + ((y - 0.08) / 0.84) * (SCREEN_H - 2 * margin)

                if smooth_x is None:
                    smooth_x, smooth_y = target_x, target_y
                else:
                    smooth_x += smoothing * (target_x - smooth_x)
                    smooth_y += smoothing * (target_y - smooth_y)

                try:
                    pyautogui.moveTo(int(smooth_x), int(smooth_y), duration=0)
                    now = time.monotonic()
                    if pinching and not previous_pinch and now - last_click_time >= click_cooldown:
                        pyautogui.click()
                        last_click_time = now
                except pyautogui.FailSafeException:
                    self.paused = True
                    self.status_queue.put("CONTROL:PAUSED")
                    self.status_queue.put("Safety stop: mouse control disabled")
                except Exception as exc:
                    self.status_queue.put(f"Mouse control error: {exc}")
                    traceback.print_exc()
                previous_pinch = pinching

            except Exception as loop_exc:
                traceback.print_exc()
                time.sleep(0.02)

    def _set_voice_mode(self, value):
        self.voice_mode = value.lower()
        self.voice_status_var.set(f"Voice mode: {value}")

    def _start_voice(self):
        if self.voice_busy or not self.running:
            return
        self.voice_busy = True
        self.listen_button.configure(state="disabled")
        self.voice_status_var.set(f"Listening ({self.voice_mode})...")
        threading.Thread(target=self._voice_worker, args=(self.voice_mode,), daemon=True).start()

    def _voice_worker(self, mode):
        try:
            recognized_text, error = self.voice_controller.listen_once(mode)
            if error:
                self.status_queue.put(f"VOICE_ERROR:{error}")
            elif recognized_text:
                self.command_queue.put(recognized_text)
                self.status_queue.put(f"Heard: {recognized_text}")
            else:
                self.status_queue.put("VOICE_ERROR:No speech was recognized")
        except Exception as exc:
            self.status_queue.put(f"VOICE_ERROR:{exc}")
            traceback.print_exc()
        finally:
            self.voice_busy = False
            self.status_queue.put("VOICE_READY")

    def _execute_voice_command(self, text):
        """Execute only allowlisted desktop commands; this runs on the action worker."""
        if not text:
            return

        # Normalize: strip punctuation, replace hyphens with space, collapse whitespace
        cleaned = text.lower().replace("-", " ").translate(str.maketrans("", "", string.punctuation))
        command = " ".join(cleaned.split())

        # Voice commands are independent of gesture cursor tracking.
        # `self.paused` disables only hand-driven cursor movement/clicking;
        # it must not block voice-driven clicks, scrolling, zoom, or system controls.

        if command in ("left click", "click"):
            pyautogui.click()
            self.status_queue.put("Action: Click")
        elif command == "double click":
            pyautogui.doubleClick()
            self.status_queue.put("Action: Double Click")
        elif command == "right click":
            pyautogui.rightClick()
            self.status_queue.put("Action: Right Click")
        elif command == "scroll up":
            pyautogui.scroll(200)
            self.status_queue.put("Action: Scroll Up")
        elif command == "scroll down":
            pyautogui.scroll(-200)
            self.status_queue.put("Action: Scroll Down")
        elif command == "zoom in":
            pyautogui.hotkey("ctrl", "+", interval=0.05)
            self.status_queue.put("Action: Zoom In")
        elif command == "zoom out":
            pyautogui.hotkey("ctrl", "-", interval=0.05)
            self.status_queue.put("Action: Zoom Out")
        elif command in ("mute", "unmute"):
            pyautogui.press("volumemute")
            self.status_queue.put("Action: Mute")
        elif command == "volume up":
            pyautogui.press("volumeup")
            self.status_queue.put("Action: Volume Up")
        elif command == "volume down":
            pyautogui.press("volumedown")
            self.status_queue.put("Action: Volume Down")
        elif command in ("move cursor left", "move left", "mouse left"):
            pyautogui.move(-100, 0)
            self.status_queue.put("Action: Move Left")
        elif command in ("move cursor right", "move right", "mouse right"):
            pyautogui.move(100, 0)
            self.status_queue.put("Action: Move Right")
        elif command in ("move cursor up", "move up", "mouse up"):
            pyautogui.move(0, -100)
            self.status_queue.put("Action: Move Up")
        elif command in ("move cursor down", "move down", "mouse down"):
            pyautogui.move(0, 100)
            self.status_queue.put("Action: Move Down")
        elif command in ("pause control", "pause", "pause mouse", "pause tracking"):
            self.paused = True
            self.status_queue.put("CONTROL:PAUSED")
            self.status_queue.put("Mouse control paused")
            self._publish_control((None, None, False))
        elif command in ("resume control", "resume", "resume mouse", "resume tracking"):
            self.paused = False
            self.status_queue.put("CONTROL:RESUMED")
            self.status_queue.put("Mouse control active")
        else:
            self.status_queue.put(f"Unknown command: {command}")

    def _toggle_pause(self):
        self.paused = not self.paused
        self.pause_button.configure(text="Enable Mouse Control" if self.paused else "Pause Mouse Control")
        self.control_var.set("Mouse control: DISABLED" if self.paused else "Mouse control: ENABLED")
        self.status_var.set("Mouse control paused" if self.paused else "Mouse control active")
        self._publish_control((None, None, False))

    def _update_dashboard(self):
        if not self.running:
            return

        while True:
            try:
                status = self.status_queue.get_nowait()
            except queue.Empty:
                break

            if status.startswith("HANDS:"):
                self.hand_var.set("Hands detected: " + status.split(":", 1)[1])
            elif status == "CONTROL:PAUSED":
                self.control_var.set("Mouse control: DISABLED")
                self.pause_button.configure(text="Enable Mouse Control")
            elif status == "CONTROL:RESUMED":
                self.control_var.set("Mouse control: ENABLED")
                self.pause_button.configure(text="Pause Mouse Control")
            elif status == "VOICE_READY":
                self.listen_button.configure(state="normal")
            elif status.startswith("VOICE_ERROR:"):
                self.voice_status_var.set(status.split(":", 1)[1])
            elif status.startswith("Heard:"):
                self.voice_status_var.set(status)
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

    def _close_app(self):
        self.running = False
        try:
            self.voice_controller.close()
        except (AttributeError, Exception):
            pass
        self.destroy()


if __name__ == "__main__":
    app = AirControlApp()
    app.mainloop()
