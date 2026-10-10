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

from core.command_router import CommandRouter
from ui.dashboard import SectionHeader, TelemetryLog, ValueSlider
from ui.theme import (
    COLOR_CHARCOAL,
    COLOR_INDIGO,
    COLOR_IVORY,
    COLOR_PANEL_BORDER,
    COLOR_PANEL_DARK,
    COLOR_PANEL_SURFACE,
    COLOR_SAGE,
    COLOR_STONE,
    COLOR_VERMILION,
    COLOR_VERMILION_HOVER,
    FONT_MONO,
    FONT_SANS,
    FONT_SERIF,
)
from vision.gesture_processor import GestureProcessor
from voice.voice_controller import VoiceController

ctk.set_appearance_mode("dark")

# Keep PyAutoGUI's emergency corner fail-safe enabled.
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.01

SCREEN_W, SCREEN_H = pyautogui.size()


class AirControlApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AirControl — Precision Desktop Control System")
        self.geometry("1260x820")
        self.minsize(1050, 680)
        self.configure(fg_color=COLOR_CHARCOAL)

        # Shared state and queues MUST exist before any worker starts.
        self.running = True
        self.paused = True
        self.gesture_processor = GestureProcessor(screen_w=SCREEN_W, screen_h=SCREEN_H)
        self.command_router = CommandRouter(app_context=self)
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
        self.last_action_var = tk.StringVar(master=self, value="Last action: None")
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

        # -------------------------------------------------------------
        # TOP HEADER: Japanese Minimal Precision Instrument Header
        # -------------------------------------------------------------
        header = ctk.CTkFrame(
            self,
            fg_color=COLOR_PANEL_DARK,
            border_color=COLOR_PANEL_BORDER,
            border_width=1,
            corner_radius=4,
        )
        header.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        # Brand mark & technical descriptor
        brand_frame = ctk.CTkFrame(header, fg_color="transparent")
        brand_frame.grid(row=0, column=0, padx=16, pady=10, sticky="w")

        title_lbl = ctk.CTkLabel(
            brand_frame,
            text="AIRCONTROL",
            font=ctk.CTkFont(family=FONT_SERIF, size=24, weight="bold"),
            text_color=COLOR_IVORY,
        )
        title_lbl.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(
            brand_frame,
            text="TOUCH-FREE DESKTOP INTERACTION SYSTEM  |  PRECISION INSTRUMENT",
            font=ctk.CTkFont(family=FONT_MONO, size=9),
            text_color=COLOR_STONE,
        )
        sub_lbl.pack(anchor="w")

        # Center Status Badges
        center_status = ctk.CTkFrame(header, fg_color="transparent")
        center_status.grid(row=0, column=1, padx=12, pady=10)

        self.engine_badge = ctk.CTkLabel(
            center_status,
            text="● ENGINE STANDBY",
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            text_color=COLOR_STONE,
        )
        self.engine_badge.pack(side="left", padx=12)

        self.cam_badge = ctk.CTkLabel(
            center_status,
            text="● SENSOR INIT",
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            text_color=COLOR_STONE,
        )
        self.cam_badge.pack(side="left", padx=12)

        # Right control button
        self.pause_button = ctk.CTkButton(
            header,
            text="Enable Mouse Control",
            command=self._toggle_pause,
            fg_color=COLOR_VERMILION,
            hover_color=COLOR_VERMILION_HOVER,
            text_color=COLOR_IVORY,
            font=ctk.CTkFont(family=FONT_SANS, size=12, weight="bold"),
            corner_radius=4,
            height=34,
            width=160,
        )
        self.pause_button.grid(row=0, column=2, padx=16, pady=10, sticky="e")

        # -------------------------------------------------------------
        # MAIN ASYMMETRIC WORKSPACE
        # -------------------------------------------------------------
        workspace = ctk.CTkFrame(self, fg_color="transparent")
        workspace.grid(row=1, column=0, padx=16, pady=4, sticky="nsew")
        workspace.grid_columnconfigure(0, weight=5)
        workspace.grid_columnconfigure(1, weight=4)
        workspace.grid_rowconfigure(0, weight=1)

        # =============================================================
        # COLUMN 0: OPTICAL SENSOR & GESTURE MATRIX
        # =============================================================
        left_panel = ctk.CTkFrame(
            workspace,
            fg_color=COLOR_PANEL_SURFACE,
            border_color=COLOR_PANEL_BORDER,
            border_width=1,
            corner_radius=4,
        )
        left_panel.grid(row=0, column=0, padx=(0, 8), pady=0, sticky="nsew")
        left_panel.grid_columnconfigure(0, weight=1)
        left_panel.grid_rowconfigure(1, weight=1)

        sec1 = SectionHeader(left_panel, "01", "Optical Sensor & Landmark Matrix", "640x480 @ 30FPS")
        sec1.grid(row=0, column=0, padx=14, pady=(12, 6), sticky="ew")

        # Video frame viewport with thin crisp border
        video_container = ctk.CTkFrame(
            left_panel,
            fg_color=COLOR_PANEL_DARK,
            border_color=COLOR_PANEL_BORDER,
            border_width=1,
            corner_radius=4,
        )
        video_container.grid(row=1, column=0, padx=14, pady=6, sticky="nsew")
        video_container.grid_columnconfigure(0, weight=1)
        video_container.grid_rowconfigure(0, weight=1)

        self.video_label = ctk.CTkLabel(
            video_container,
            text="ACQUIRING OPTICAL SENSOR FEED...\n\nPLACE HAND IN VIEW TO ENGAGE MATRIX",
            font=ctk.CTkFont(family=FONT_MONO, size=12),
            text_color=COLOR_STONE,
        )
        self.video_label.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")

        # Telemetry bar under video
        telemetry_bar = ctk.CTkFrame(
            left_panel,
            fg_color=COLOR_PANEL_DARK,
            border_color=COLOR_PANEL_BORDER,
            border_width=1,
            corner_radius=4,
        )
        telemetry_bar.grid(row=2, column=0, padx=14, pady=(6, 8), sticky="ew")
        telemetry_bar.grid_columnconfigure(1, weight=1)

        self.hands_badge = ctk.CTkLabel(
            telemetry_bar,
            textvariable=self.hand_var,
            font=ctk.CTkFont(family=FONT_MONO, size=11),
            text_color=COLOR_IVORY,
        )
        self.hands_badge.grid(row=0, column=0, padx=12, pady=6, sticky="w")

        self.state_badge = ctk.CTkLabel(
            telemetry_bar,
            textvariable=self.control_var,
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            text_color=COLOR_STONE,
        )
        self.state_badge.grid(row=0, column=1, padx=12, pady=6)

        self.failsafe_badge = ctk.CTkLabel(
            telemetry_bar,
            text="FAILSAFE: CORNER ARMED",
            font=ctk.CTkFont(family=FONT_MONO, size=10),
            text_color=COLOR_SAGE,
        )
        self.failsafe_badge.grid(row=0, column=2, padx=12, pady=6, sticky="e")

        # Quick reference protocol matrix
        ref_card = ctk.CTkFrame(
            left_panel,
            fg_color=COLOR_PANEL_DARK,
            border_color=COLOR_PANEL_BORDER,
            border_width=1,
            corner_radius=4,
        )
        ref_card.grid(row=3, column=0, padx=14, pady=(0, 10), sticky="ew")
        ref_card.grid_columnconfigure(0, weight=1)
        ref_card.grid_columnconfigure(1, weight=1)

        # Left sub-column: Gestures
        g_box = ctk.CTkFrame(ref_card, fg_color="transparent")
        g_box.grid(row=0, column=0, padx=10, pady=6, sticky="nsew")

        ctk.CTkLabel(
            g_box,
            text="[ GESTURE PROTOCOL ]",
            font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
            text_color=COLOR_VERMILION,
        ).pack(anchor="w")

        ctk.CTkLabel(
            g_box,
            text="• POSITION: 1.5–3 ft from lens\n• MOVE: Index finger tip (1€ Filter)\n• CLICK: Pinch thumb + index\n• FAIL-SAFE: Throw mouse to top-left",
            font=ctk.CTkFont(family=FONT_MONO, size=9),
            text_color=COLOR_STONE,
            justify="left",
        ).pack(anchor="w", pady=(2, 0))

        # Right sub-column: Voice
        v_box = ctk.CTkFrame(ref_card, fg_color="transparent")
        v_box.grid(row=0, column=1, padx=10, pady=6, sticky="nsew")

        ctk.CTkLabel(
            v_box,
            text="[ VOICE PROTOCOL ]",
            font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
            text_color=COLOR_INDIGO,
        ).pack(anchor="w")

        ctk.CTkLabel(
            v_box,
            text="• APPS: 'Open Chrome' | 'Launch Notepad'\n• WEB: 'Open LinkedIn / GitHub / YouTube in Chrome'\n• ACTIONS: 'Click' | 'Scroll Up/Down' | 'Zoom In/Out'\n• AUDIO: 'Volume Up/Down' | 'Mute'",
            font=ctk.CTkFont(family=FONT_MONO, size=9),
            text_color=COLOR_STONE,
            justify="left",
        ).pack(anchor="w", pady=(2, 0))

        # =============================================================
        # COLUMN 1: VOICE COMMAND CENTER & INSTRUMENT AUDIT LEDGER
        # =============================================================
        right_panel = ctk.CTkFrame(workspace, fg_color="transparent")
        right_panel.grid(row=0, column=1, padx=(8, 0), pady=0, sticky="nsew")
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(2, weight=1)  # Audit log expands

        # --- Section [ 02 ] Voice Interface ---
        voice_card = ctk.CTkFrame(
            right_panel,
            fg_color=COLOR_PANEL_SURFACE,
            border_color=COLOR_PANEL_BORDER,
            border_width=1,
            corner_radius=4,
        )
        voice_card.grid(row=0, column=0, pady=(0, 8), sticky="ew")
        voice_card.grid_columnconfigure(0, weight=1)

        sec2 = SectionHeader(voice_card, "02", "Acoustic Command Translator")
        sec2.grid(row=0, column=0, padx=12, pady=(10, 6), sticky="ew")

        # Control Row inside voice card: Mode + Recording Stamp
        voice_ctrl_row = ctk.CTkFrame(voice_card, fg_color="transparent")
        voice_ctrl_row.grid(row=1, column=0, padx=12, pady=4, sticky="ew")

        self.rec_badge = ctk.CTkLabel(
            voice_ctrl_row,
            text="● MIC STANDBY",
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            text_color=COLOR_STONE,
        )
        self.rec_badge.pack(side="left")

        self.voice_mode_button = ctk.CTkSegmentedButton(
            voice_ctrl_row,
            values=["Online", "Offline"],
            command=self._set_voice_mode,
            selected_color=COLOR_INDIGO,
            selected_hover_color="#364761",
            unselected_color=COLOR_PANEL_DARK,
            text_color=COLOR_IVORY,
            font=ctk.CTkFont(family=FONT_SANS, size=11),
            height=26,
            corner_radius=4,
        )
        self.voice_mode_button.set("Online")
        self.voice_mode_button.pack(side="right")

        # Voice status display
        v_disp = ctk.CTkFrame(
            voice_card,
            fg_color=COLOR_PANEL_DARK,
            border_color=COLOR_PANEL_BORDER,
            border_width=1,
            corner_radius=4,
        )
        v_disp.grid(row=2, column=0, padx=12, pady=6, sticky="ew")
        v_disp.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            v_disp,
            text="READOUT:",
            font=ctk.CTkFont(family=FONT_MONO, size=10),
            text_color=COLOR_STONE,
        ).grid(row=0, column=0, padx=(8, 4), pady=6, sticky="w")

        ctk.CTkLabel(
            v_disp,
            textvariable=self.voice_status_var,
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            text_color=COLOR_IVORY,
            wraplength=380,
            justify="left",
        ).grid(row=0, column=1, padx=4, pady=6, sticky="w")

        # Listen Action Button
        self.listen_button = ctk.CTkButton(
            voice_card,
            text="Listen for Command",
            command=self._start_voice,
            fg_color=COLOR_INDIGO,
            hover_color="#364761",
            text_color=COLOR_IVORY,
            font=ctk.CTkFont(family=FONT_SANS, size=12, weight="bold"),
            corner_radius=4,
            height=32,
        )
        self.listen_button.grid(row=3, column=0, padx=12, pady=(4, 10), sticky="ew")

        # --- Section [ 03 ] Audit Log ---
        sec3 = SectionHeader(right_panel, "03", "Chronological Instrument Audit Log")
        sec3.grid(row=1, column=0, pady=(4, 4), sticky="ew")

        self.telemetry_log = TelemetryLog(right_panel)
        self.telemetry_log.grid(row=2, column=0, pady=0, sticky="nsew")

        # --- Section [ 04 ] Calibration Desk ---
        calib_card = ctk.CTkFrame(
            right_panel,
            fg_color=COLOR_PANEL_SURFACE,
            border_color=COLOR_PANEL_BORDER,
            border_width=1,
            corner_radius=4,
        )
        calib_card.grid(row=3, column=0, pady=(8, 0), sticky="ew")
        calib_card.grid_columnconfigure(0, weight=1)

        sec4 = SectionHeader(calib_card, "04", "Calibration & Filter Parameters")
        sec4.grid(row=0, column=0, padx=12, pady=(8, 4), sticky="ew")

        self.slider_sens = ValueSlider(
            calib_card,
            label="Sensitivity Scale",
            from_=0.4,
            to=2.5,
            default=1.0,
            unit="x",
            on_change=lambda val: self.gesture_processor.update_settings(sensitivity=val),
        )
        self.slider_sens.grid(row=1, column=0, padx=12, pady=3, sticky="ew")

        self.slider_filter = ValueSlider(
            calib_card,
            label="1€ Filter Cutoff",
            from_=0.2,
            to=2.5,
            default=0.8,
            unit="Hz",
            on_change=lambda val: self.gesture_processor.update_settings(min_cutoff=val),
        )
        self.slider_filter.grid(row=2, column=0, padx=12, pady=3, sticky="ew")

        self.slider_cooldown = ValueSlider(
            calib_card,
            label="Click Debounce",
            from_=0.15,
            to=0.80,
            default=0.40,
            unit="s",
            on_change=lambda val: self.gesture_processor.update_settings(click_cooldown=val),
        )
        self.slider_cooldown.grid(row=3, column=0, padx=12, pady=(3, 8), sticky="ew")

        # -------------------------------------------------------------
        # BOTTOM STATUS STRIP
        # -------------------------------------------------------------
        footer = ctk.CTkFrame(
            self,
            fg_color=COLOR_PANEL_DARK,
            border_color=COLOR_PANEL_BORDER,
            border_width=1,
            corner_radius=4,
        )
        footer.grid(row=2, column=0, padx=16, pady=(6, 12), sticky="ew")
        footer.grid_columnconfigure(1, weight=1)

        self.system_status_label = ctk.CTkLabel(
            footer,
            textvariable=self.status_var,
            font=ctk.CTkFont(family=FONT_MONO, size=10),
            text_color=COLOR_IVORY,
        )
        self.system_status_label.grid(row=0, column=0, padx=14, pady=6, sticky="w")

        self.action_display_label = ctk.CTkLabel(
            footer,
            textvariable=self.last_action_var,
            font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
            text_color=COLOR_SAGE,
        )
        self.action_display_label.grid(row=0, column=1, padx=14, pady=6, sticky="e")

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

        # Resilient camera opening: try DirectShow first on Windows, then standard index 0
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            self.status_queue.put("CAMERA_ERROR:Webcam unavailable. Check permissions or close other apps using camera.")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        consecutive_drops = 0

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
                        consecutive_drops += 1
                        if consecutive_drops == 10:
                            self.status_queue.put("CAMERA_ERROR:Camera feed interrupted. Reconnecting...")
                        if consecutive_drops > 25:
                            cap.release()
                            time.sleep(0.5)
                            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                            if not cap.isOpened():
                                cap = cv2.VideoCapture(0)
                            consecutive_drops = 0
                            if cap.isOpened():
                                self.status_queue.put("Camera connected")
                        time.sleep(0.05)
                        continue

                    consecutive_drops = 0
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

                        processor = self.__dict__.get("gesture_processor")
                        if processor is not None:
                            pinching, pinch_ratio = processor.calculate_pinch(
                                index_tip.x, index_tip.y,
                                thumb_tip.x, thumb_tip.y,
                                wrist.x, wrist.y,
                                middle_mcp.x, middle_mcp.y,
                            )
                        else:
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
        processor = self.__dict__.get("gesture_processor")
        if processor is None:
            processor = self.gesture_processor = GestureProcessor(SCREEN_W, SCREEN_H)

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
                            processor.reset()
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

                if self.paused:
                    processor.reset()
                    continue

                screen_x, screen_y, trigger_click = processor.process_frame(x, y, pinching)

                if screen_x is not None and screen_y is not None:
                    try:
                        pyautogui.moveTo(screen_x, screen_y, duration=0)
                        if trigger_click:
                            pyautogui.click()
                            self.status_queue.put("Action: Gesture Click")
                    except pyautogui.FailSafeException:
                        self.paused = True
                        processor.reset()
                        self.status_queue.put("CONTROL:PAUSED")
                        self.status_queue.put("Safety stop: mouse control disabled")
                    except Exception as exc:
                        self.status_queue.put(f"Mouse control error: {exc}")
                        traceback.print_exc()

            except Exception as loop_exc:
                traceback.print_exc()
                time.sleep(0.02)

    def _set_voice_mode(self, value):
        self.voice_mode = value.lower()
        if self.voice_mode == "offline" and not self.voice_controller.model_path.exists():
            self.voice_status_var.set("Warning: Vosk model missing. Offline mode unavailable.")
        else:
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
            recognized_text, error = self.voice_controller.listen_once(
                mode=mode,
                on_status=lambda msg: self.status_queue.put(f"VOICE_STATUS:{msg}"),
            )
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
        router = self.__dict__.get("command_router")
        if router is None:
            router = self.command_router = CommandRouter(app_context=self)
        router.execute(text, app=self)

    def _toggle_pause(self):
        self.paused = not self.paused
        processor = self.__dict__.get("gesture_processor")
        if processor:
            processor.reset()
        self.pause_button.configure(text="Enable Mouse Control" if self.paused else "Pause Mouse Control")
        self.control_var.set("Mouse control: DISABLED" if self.paused else "Mouse control: ENABLED")
        self.status_var.set("Mouse control paused" if self.paused else "Mouse control active")
        self.last_action_var.set("Last action: Mouse control paused" if self.paused else "Last action: Mouse control active")
        self._publish_control((None, None, False))

    def _update_dashboard(self):
        if not self.running:
            return

        t_log = self.__dict__.get("telemetry_log")
        e_badge = self.__dict__.get("engine_badge")
        c_badge = self.__dict__.get("cam_badge")
        r_badge = self.__dict__.get("rec_badge")

        while True:
            try:
                status = self.status_queue.get_nowait()
            except queue.Empty:
                break

            if status.startswith("HANDS:"):
                cnt = status.split(":", 1)[1]
                self.hand_var.set("Hands detected: " + cnt)
            elif status == "CONTROL:PAUSED":
                self.control_var.set("Mouse control: DISABLED")
                self.pause_button.configure(text="Enable Mouse Control")
                if e_badge:
                    e_badge.configure(text="● ENGINE PAUSED", text_color=COLOR_STONE)
                if t_log:
                    t_log.append_entry("SAFETY", "Mouse control paused", "HOLD")
            elif status == "CONTROL:RESUMED":
                self.control_var.set("Mouse control: ENABLED")
                self.pause_button.configure(text="Pause Mouse Control")
                if e_badge:
                    e_badge.configure(text="● ENGINE ACTIVE", text_color=COLOR_SAGE)
                if t_log:
                    t_log.append_entry("ENGINE", "Mouse control active", "ONLINE")
            elif status == "VOICE_READY":
                self.listen_button.configure(state="normal")
                if r_badge:
                    r_badge.configure(text="● MIC STANDBY", text_color=COLOR_STONE)
            elif status.startswith("VOICE_STATUS:"):
                msg = status.split(":", 1)[1]
                self.voice_status_var.set(msg)
                if "Listening" in msg and r_badge:
                    r_badge.configure(text="● RECORDING...", text_color=COLOR_VERMILION)
                if t_log:
                    t_log.append_entry("VOICE", msg[:36], "INFO")
            elif status.startswith("VOICE_ERROR:"):
                err = status.split(":", 1)[1]
                self.voice_status_var.set(err)
                if r_badge:
                    r_badge.configure(text="● MIC ERROR", text_color=COLOR_VERMILION)
                if t_log:
                    t_log.append_entry("VOICE", err[:36], "ERROR")
            elif status.startswith("Heard:"):
                self.voice_status_var.set(status)
                if t_log:
                    t_log.append_entry("VOICE", status[:36], "RECOG")
            elif status.startswith("CAMERA_ERROR:"):
                msg = status.split(":", 1)[1]
                self.status_var.set(f"Camera: {msg}")
                self.video_label.configure(image="", text=f"Camera Unavailable\n\n{msg}")
                if c_badge:
                    c_badge.configure(text="● CAM ERROR", text_color=COLOR_VERMILION)
                if t_log:
                    t_log.append_entry("CAMERA", msg[:36], "ERROR")
            elif status == "Camera connected":
                self.status_var.set("Camera: Connected")
                if c_badge:
                    c_badge.configure(text="● CAM ONLINE", text_color=COLOR_SAGE)
                if t_log:
                    t_log.append_entry("CAMERA", "Optical sensor connected", "ONLINE")
            elif status.startswith("Action:"):
                act = status.split(":", 1)[1].strip()
                self.last_action_var.set(f"Last action: {act}")
                self.status_var.set(status)
                src = "GESTURE" if "Gesture" in act else "VOICE"
                if t_log:
                    t_log.append_entry(src, act[:36], "SUCCESS")
            else:
                self.status_var.set(status)
                if t_log:
                    t_log.append_entry("SYSTEM", status[:36], "EVENT")

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
