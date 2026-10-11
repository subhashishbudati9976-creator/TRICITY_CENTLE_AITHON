"""
AirControl — Headless Engine Core for Web and Desktop
Encapsulates computer vision gestures, PyAutoGUI control, and voice command pipelines.
"""

import math
import queue
import threading
import time
import traceback
from typing import Dict, Any, List, Optional

import cv2
import mediapipe as mp
import pyautogui

from core.command_router import CommandRouter
from vision.gesture_processor import GestureProcessor
from vision.hand_gesture_detector import HandGestureDetector
from voice.voice_controller import (
    VoiceController,
    match_start_wake_phrase,
    match_stop_wake_phrase,
)

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.01

SCREEN_W, SCREEN_H = pyautogui.size()


class AirControlEngine:
    def __init__(self):
        self.running = True
        self.paused = True
        self.camera_connected = False
        self.current_action_description = ""

        # Control Modes: 'cursor' (mouse tracking & pinch click) vs 'gesture' (keyboard shortcuts)
        self.control_mode: str = "cursor"
        self.gesture_keys_enabled: bool = True

        # Processors
        self.gesture_processor = GestureProcessor(screen_w=SCREEN_W, screen_h=SCREEN_H)
        self.hand_gesture_detector = HandGestureDetector()
        self.command_router = CommandRouter(
            app_context=self, confirmation_fn=self._action_confirmation
        )
        self.voice_controller = VoiceController()
        self.voice_mode = "online"
        self.voice_busy = False
        self.voice_listening_active: bool = False

        # Feedback-loop protection
        self.browser_speaking: bool = False
        self.last_speech_end_time: float = 0.0

        # Queues
        self.frame_queue = queue.Queue(maxsize=1)
        self.control_queue = queue.Queue(maxsize=2)
        self.status_queue = queue.Queue()
        self.assistant_queue = queue.Queue()
        self.command_queue = queue.Queue()
        self.spoken_queue = queue.Queue()

        self.task_cancel_event = threading.Event()
        self.task_active_event = threading.Event()

        # Telemetry State
        self.hands_detected = 0
        self.detected_gesture: str = "None"
        self.gesture_action: str = "None"
        self.gesture_progress: float = 0.0
        self.voice_status = "Voice: Ready"
        self.recognized_text = "No request recognized yet."
        self.assistant_status = "Ready. Built-in intents & Gemini fallback active."
        self.last_action = "Last action: None"
        self.system_status = "Engine initialized."
        self.audit_logs: List[Dict[str, str]] = []

        self._latest_jpeg: Optional[bytes] = None
        self._jpeg_lock = threading.Lock()

        # Thread workers
        self.camera_thread: Optional[threading.Thread] = None
        self.mouse_thread: Optional[threading.Thread] = None
        self.wake_thread: Optional[threading.Thread] = None

    def start(self):
        self.running = True
        self.append_log("SYS", "AirControl Engine Online", "ONLINE")
        self.camera_thread = threading.Thread(target=self._camera_worker, daemon=True)
        self.mouse_thread = threading.Thread(target=self._mouse_worker, daemon=True)
        self.wake_thread = threading.Thread(target=self._wake_worker, daemon=True)
        self.camera_thread.start()
        self.mouse_thread.start()
        self.wake_thread.start()

    def stop(self):
        self.running = False
        self.paused = True
        if self.gesture_processor:
            self.gesture_processor.reset()
        if self.hand_gesture_detector:
            self.hand_gesture_detector.reset()

    def append_log(self, source: str, event: str, status: str = "OK"):
        now_str = time.strftime("%H:%M:%S")
        entry = {
            "timestamp": now_str,
            "source": source.upper()[:8],
            "event": event[:48],
            "status": status.upper()[:10],
        }
        self.audit_logs.append(entry)
        if len(self.audit_logs) > 200:
            self.audit_logs.pop(0)
        return entry

    def _action_confirmation(self, prompt: str) -> bool:
        self.append_log("SAFETY", f"Auto-confirmed: {prompt[:30]}", "CONFIRMED")
        return True

    def _publish_control(self, command):
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

    def set_control_mode(self, mode: str) -> str:
        """Switch between 'cursor' (mouse tracking) and 'gesture' (shortcut keys)."""
        norm = (mode or "").lower().strip()
        if norm in ("cursor", "mouse"):
            self.control_mode = "cursor"
            self.hand_gesture_detector.reset()
            self.append_log("MODE", "Switched to Cursor Mode", "CONFIG")
            self.status_queue.put("CONTROL_MODE:cursor")
        elif norm in ("gesture", "gesture_key", "gesture-key", "keyboard"):
            self.control_mode = "gesture"
            self.gesture_processor.reset()
            self.append_log("MODE", "Switched to Gesture-Key Mode", "CONFIG")
            self.status_queue.put("CONTROL_MODE:gesture")
        return self.control_mode

    def toggle_control_mode(self) -> str:
        new_mode = "gesture" if self.control_mode == "cursor" else "cursor"
        return self.set_control_mode(new_mode)

    def toggle_gesture_keys(self) -> bool:
        self.gesture_keys_enabled = not self.gesture_keys_enabled
        st = "ENABLED" if self.gesture_keys_enabled else "DISABLED"
        self.append_log("GESTURE", f"Gesture keys {st}", "CONFIG")
        return self.gesture_keys_enabled

    def set_speech_state(self, speaking: bool):
        """Called by web server when browser Web Speech API starts or finishes."""
        self.browser_speaking = bool(speaking)
        if not speaking:
            self.last_speech_end_time = time.monotonic()

    def queue_spoken_text(self, text: str):
        if text:
            self.spoken_queue.put(text)

    def _camera_worker(self):
        hands_module = mp.solutions.hands
        drawing = mp.solutions.drawing_utils

        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            self.status_queue.put("CAMERA_ERROR:Webcam unavailable. Check permissions or camera index.")
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
                self.camera_connected = True
                self.status_queue.put("Camera connected")
                while self.running:
                    ok, frame = cap.read()
                    if not ok:
                        consecutive_drops += 1
                        if consecutive_drops == 10:
                            self.camera_connected = False
                            self.status_queue.put("CAMERA_ERROR:Camera feed interrupted.")
                        if consecutive_drops > 25:
                            cap.release()
                            time.sleep(0.5)
                            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                            if not cap.isOpened():
                                cap = cv2.VideoCapture(0)
                            consecutive_drops = 0
                            if cap.isOpened():
                                self.camera_connected = True
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
                        landmarks = detected_hands[0]
                        index_tip = landmarks.landmark[8]
                        thumb_tip = landmarks.landmark[4]
                        wrist = landmarks.landmark[0]
                        middle_mcp = landmarks.landmark[9]

                        if self.control_mode == "cursor":
                            self.hand_gesture_detector.reset()
                            if self.paused:
                                self.gesture_processor.reset_pinch_detection()
                                pinching, pinch_ratio = False, 1.0
                            else:
                                pinching, pinch_ratio = self.gesture_processor.calculate_pinch(
                                    index_tip.x, index_tip.y,
                                    thumb_tip.x, thumb_tip.y,
                                    wrist.x, wrist.y,
                                    middle_mcp.x, middle_mcp.y,
                                )

                            cv2.putText(
                                frame, f"{'PINCH' if pinching else 'OPEN'} {pinch_ratio:.2f} [CURSOR MODE]", (20, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                                (0, 255, 0) if pinching else (255, 255, 255), 2,
                            )
                            self.detected_gesture = "Index Tip"
                            self.gesture_action = "Pinch Click" if pinching else "Cursor Movement"
                            self.gesture_progress = 1.0 if pinching else 0.0
                            self._publish_control((index_tip.x, index_tip.y, pinching, None))

                        else:
                            # GESTURE-KEY MODE
                            self.gesture_processor.reset_pinch_detection()
                            if self.gesture_keys_enabled and not self.paused:
                                g_name, g_act, g_prog, g_trigger = self.hand_gesture_detector.process_landmarks(
                                    landmarks.landmark, handedness="Right"
                                )
                                self.detected_gesture = g_name or "None"
                                self.gesture_action = g_act or "None"
                                self.gesture_progress = g_prog
                                if g_trigger is not None:
                                    self._publish_control((None, None, False, g_trigger))
                                else:
                                    self._publish_control((None, None, False, None))
                            else:
                                self.hand_gesture_detector.reset()
                                self.detected_gesture = "None"
                                self.gesture_action = "Paused" if self.paused else "Disabled"
                                self.gesture_progress = 0.0
                                self._publish_control((None, None, False, None))

                            label_txt = f"{self.detected_gesture} -> {self.gesture_action}"
                            pct = int(self.gesture_progress * 100)
                            cv2.putText(
                                frame, f"[GESTURE MODE] {label_txt} ({pct}%)", (20, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                                (0, 255, 255) if self.gesture_progress > 0.5 else (200, 200, 200), 2,
                            )
                    else:
                        self.gesture_processor.reset_pinch_detection()
                        self.hand_gesture_detector.reset()
                        self.detected_gesture = "None"
                        self.gesture_action = "None"
                        self.gesture_progress = 0.0
                        self._publish_control((None, None, False, None))

                    self.status_queue.put(f"HANDS:{len(detected_hands)}")

                    # Encode to JPEG for fast HTTP MJPEG streaming
                    ret, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                    if ret:
                        with self._jpeg_lock:
                            self._latest_jpeg = jpeg.tobytes()

                    time.sleep(0.015)
        except Exception as exc:
            self.status_queue.put(f"CAMERA_ERROR:{exc}")
            traceback.print_exc()
        finally:
            self.camera_connected = False
            self.gesture_processor.reset_pinch_detection()
            self.hand_gesture_detector.reset()
            cap.release()

    def _mouse_worker(self):
        processor = self.gesture_processor

        while self.running:
            try:
                # 1. Drain pending voice commands
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
                            self.hand_gesture_detector.reset()
                            self.status_queue.put("CONTROL:PAUSED")
                            self.status_queue.put("Safety stop: mouse control disabled")
                            self.append_log("SAFETY", "Failsafe corner: Mouse paused", "HOLD")
                        except Exception as exc:
                            self.status_queue.put(f"Command error: {exc}")
                            self.append_log("COMMAND", f"Error: {exc}", "ERROR")
                            traceback.print_exc()

                # 2. Process control sample
                try:
                    ctrl = self.control_queue.get(timeout=0.02)
                except queue.Empty:
                    continue

                x, y, pinching, *extra = ctrl
                gesture_trigger = extra[0] if extra else None

                # Execute gesture shortcut trigger if present
                if gesture_trigger is not None and not self.paused and self.gesture_keys_enabled:
                    try:
                        act_type = gesture_trigger.get("type")
                        act_label = gesture_trigger.get("action", gesture_trigger.get("action_label", "Gesture"))
                        gest_name = gesture_trigger.get("name", "Hand Shape")

                        if act_type == "press":
                            for k in gesture_trigger.get("keys", []):
                                pyautogui.press(k)
                        elif act_type == "hotkey":
                            pyautogui.hotkey(*gesture_trigger.get("keys", []), interval=0.03)
                        elif act_type == "right_click":
                            pyautogui.rightClick()
                        elif act_type == "scroll":
                            delta = gesture_trigger.get("delta", 150)
                            pyautogui.scroll(delta)
                        elif act_type == "zoom":
                            direction = gesture_trigger.get("direction", "in")
                            if direction == "in":
                                pyautogui.hotkey("ctrl", "+", interval=0.03)
                            else:
                                pyautogui.hotkey("ctrl", "-", interval=0.03)

                        msg = f"{gest_name} -> {act_label}"
                        self.status_queue.put(f"Action: Gesture {msg}")
                        self.append_log("GESTURE", msg, "SUCCESS")
                    except pyautogui.FailSafeException:
                        self.paused = True
                        processor.reset()
                        self.hand_gesture_detector.reset()
                        self.status_queue.put("CONTROL:PAUSED")
                        self.status_queue.put("Safety stop: mouse control disabled")
                        self.append_log("SAFETY", "Failsafe corner: Mouse paused", "HOLD")
                    except Exception as exc:
                        self.status_queue.put(f"Gesture action error: {exc}")
                        self.append_log("GESTURE", f"Error: {exc}", "ERROR")

                # Process cursor movement and click in cursor mode
                if x is not None and y is not None and self.control_mode == "cursor":
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
                                self.append_log("GESTURE", "Pinch Click", "SUCCESS")
                        except pyautogui.FailSafeException:
                            self.paused = True
                            processor.reset()
                            self.hand_gesture_detector.reset()
                            self.status_queue.put("CONTROL:PAUSED")
                            self.status_queue.put("Safety stop: mouse control disabled")
                            self.append_log("SAFETY", "Failsafe corner: Mouse paused", "HOLD")
                        except Exception as exc:
                            self.status_queue.put(f"Mouse control error: {exc}")
                            self.append_log("MOUSE", f"Error: {exc}", "ERROR")
                            traceback.print_exc()

            except Exception:
                time.sleep(0.02)

    def _wake_worker(self):
        """
        Runs continuous background listening:
        - When stopped: lightweight wake-phrase listener ('Hey AirControl, start listening').
        - When active: continuous voice command recognition & stop phrase ('Hey AirControl, stop listening').
        - Feedback-loop protection: silences mic when browser is speaking + 500ms.
        """
        while self.running:
            try:
                # 1. Feedback-loop protection
                if self.browser_speaking or (time.monotonic() - self.last_speech_end_time < 0.5):
                    time.sleep(0.06)
                    continue

                # 2. When stopped, listen ONLY for start wake phrases
                if not self.voice_listening_active:
                    detected, phrase, err = self.voice_controller.listen_wake_phrase(
                        mode=self.voice_mode, timeout=2, phrase_time_limit=3
                    )
                    if detected:
                        self.voice_listening_active = True
                        self.voice_status = f"Listening ({self.voice_mode})..."
                        self.status_queue.put("WAKE_ACTIVE:Listening")
                        self.append_log("VOICE", "Wake phrase detected: Listening", "ONLINE")
                        self.spoken_queue.put("Listening")
                    time.sleep(0.05)
                    continue

                # 3. When active, listen for speech commands or stop phrase
                if self.voice_busy or self.task_active_event.is_set():
                    time.sleep(0.05)
                    continue

                self.voice_status = f"Listening ({self.voice_mode})..."
                recognized_text, error = self.voice_controller.listen_once(
                    mode=self.voice_mode,
                    on_status=lambda msg: self.status_queue.put(f"VOICE_STATUS:{msg}"),
                )

                # Check if browser began speaking during recognition
                if self.browser_speaking or (time.monotonic() - self.last_speech_end_time < 0.5):
                    continue

                if error:
                    time.sleep(0.1)
                    continue

                if recognized_text:
                    if match_stop_wake_phrase(recognized_text):
                        self.voice_listening_active = False
                        self.voice_status = "Voice: Ready"
                        self.status_queue.put("WAKE_INACTIVE:Stopped")
                        self.append_log("VOICE", "Stop phrase detected: Stopped", "STANDBY")
                        self.spoken_queue.put("Stopped")
                        continue

                    # Recognized a command
                    self.assistant_queue.put(f"REQUEST:{recognized_text}")
                    self.status_queue.put(f"Heard: {recognized_text}")
                    normalized = " ".join(recognized_text.lower().replace("-", " ").split())
                    if normalized in {
                        "cancel task", "cancel current task", "stop current task", "cancel request"
                    }:
                        self.task_cancel_event.set()
                        self.assistant_queue.put("FINAL:Cancellation requested by voice.")
                        self.spoken_queue.put("Task cancelled")
                    elif self.task_cancel_event.is_set():
                        self.assistant_queue.put("FINAL:Voice request cancelled.")
                    else:
                        self.command_queue.put(recognized_text)

            except Exception as exc:
                time.sleep(0.1)

    def _execute_voice_command(self, raw_command: str):
        self.task_active_event.set()
        try:
            self.status_queue.put(f"VOICE_STATUS:Executing: {raw_command}")
            success, status_text, _label = self.command_router.execute(
                raw_command, app=self
            )
            if success:
                self.status_queue.put(f"Action: {status_text}")
                self.assistant_queue.put(f"FINAL:{status_text}")
                self.spoken_queue.put(status_text)
            else:
                self.status_queue.put(f"VOICE_ERROR:{status_text}")
                self.assistant_queue.put(f"ERROR:{status_text}")
                self.spoken_queue.put(status_text)
        except Exception as exc:
            self.status_queue.put(f"VOICE_ERROR:{exc}")
            self.assistant_queue.put(f"ERROR:{exc}")
        finally:
            self.task_active_event.clear()
            self.voice_busy = False
            self.status_queue.put("VOICE_READY")

    def toggle_pause(self) -> bool:
        self.paused = not self.paused
        if self.gesture_processor:
            self.gesture_processor.reset()
        if self.hand_gesture_detector:
            self.hand_gesture_detector.reset()
        if self.paused:
            self.append_log("CONTROL", "Control paused", "PAUSED")
            self.system_status = "Control paused"
            self.last_action = "Last action: Control paused"
        else:
            self.append_log("CONTROL", "Control active", "ONLINE")
            self.system_status = "Control active"
            self.last_action = "Last action: Control active"
        self._publish_control((None, None, False, None))
        return self.paused

    def set_voice_mode(self, mode: str) -> str:
        self.voice_mode = mode.lower()
        if self.voice_mode == "offline" and not self.voice_controller.model_path.exists():
            self.voice_status = "Warning: Vosk model missing. Offline unavailable."
            self.append_log("VOICE", "Vosk model missing for offline mode", "WARN")
        else:
            self.voice_status = f"Voice mode: {mode.capitalize()}"
            self.append_log("VOICE", f"Switched to {mode.capitalize()} mode", "CONFIG")
        return self.voice_mode

    def start_voice(self) -> bool:
        """Trigger voice command listening (active listening mode)."""
        self.voice_listening_active = True
        self.task_cancel_event.clear()
        self.recognized_text = "Listening for a request..."
        self.voice_status = f"Listening ({self.voice_mode})..."
        self.status_queue.put("WAKE_ACTIVE:Listening")
        self.append_log("VOICE", f"Microphone active ({self.voice_mode})", "LISTENING")
        return True

    def stop_voice(self) -> bool:
        """Stop active voice listening (returns to wake-phrase standby)."""
        self.voice_listening_active = False
        self.voice_status = "Voice: Standby"
        self.status_queue.put("WAKE_INACTIVE:Stopped")
        self.append_log("VOICE", "Voice listening stopped", "STANDBY")
        self.spoken_queue.put("Stopped")
        return True

    def cancel_current_task(self):
        if self.task_active_event.is_set() or self.voice_busy:
            self.task_cancel_event.set()
            self.assistant_status = "Cancellation requested."
            self.append_log("TASK", "Task cancelled by user", "CANCEL")
        else:
            self.assistant_status = "No active task to cancel."

    def update_calibration(
        self,
        sensitivity: Optional[float] = None,
        min_cutoff: Optional[float] = None,
        click_cooldown: Optional[float] = None,
        gesture_hold_normal: Optional[float] = None,
        gesture_hold_dangerous: Optional[float] = None,
        gesture_cooldown: Optional[float] = None,
        scroll_speed: Optional[int] = None,
    ):
        kwargs = {}
        if sensitivity is not None:
            kwargs["sensitivity"] = float(sensitivity)
        if min_cutoff is not None:
            kwargs["min_cutoff"] = float(min_cutoff)
        if click_cooldown is not None:
            kwargs["click_cooldown"] = float(click_cooldown)
        self.gesture_processor.update_settings(**kwargs)

        if gesture_hold_normal is not None:
            self.hand_gesture_detector.hold_time_normal = float(gesture_hold_normal)
        if gesture_hold_dangerous is not None:
            self.hand_gesture_detector.hold_time_dangerous = float(gesture_hold_dangerous)
        if gesture_cooldown is not None:
            self.hand_gesture_detector.cooldown_seconds = float(gesture_cooldown)
        if scroll_speed is not None:
            self.hand_gesture_detector.scroll_speed = int(scroll_speed)

        self.append_log("CALIB", "Updated calibration parameters", "CONFIG")

    def get_latest_jpeg(self) -> Optional[bytes]:
        with self._jpeg_lock:
            return self._latest_jpeg

    def drain_events(self) -> List[Dict[str, Any]]:
        events = []
        while True:
            try:
                status = self.status_queue.get_nowait()
            except queue.Empty:
                break

            if status.startswith("HANDS:"):
                cnt = int(status.split(":", 1)[1])
                self.hands_detected = cnt
                events.append({"type": "HANDS", "count": cnt})
            elif status == "CONTROL:PAUSED":
                self.paused = True
                events.append({"type": "CONTROL", "paused": True})
            elif status == "CONTROL:RESUMED":
                self.paused = False
                events.append({"type": "CONTROL", "paused": False})
            elif status == "VOICE_READY":
                self.voice_busy = False
                events.append({"type": "VOICE_READY"})
            elif status.startswith("VOICE_STATUS:"):
                msg = status.split(":", 1)[1]
                self.voice_status = msg
                self.append_log("VOICE", msg[:36], "INFO")
                events.append({"type": "VOICE_STATUS", "message": msg})
            elif status.startswith("VOICE_ERROR:"):
                err = status.split(":", 1)[1]
                self.voice_status = err
                self.append_log("VOICE", err[:36], "ERROR")
                events.append({"type": "VOICE_ERROR", "error": err})
            elif status.startswith("Heard:"):
                self.voice_status = status
                self.append_log("VOICE", status[:36], "RECOG")
                events.append({"type": "VOICE_HEARD", "text": status})
            elif status.startswith("WAKE_ACTIVE:"):
                events.append({"type": "WAKE_STATE", "active": True})
            elif status.startswith("WAKE_INACTIVE:"):
                events.append({"type": "WAKE_STATE", "active": False})
            elif status.startswith("CONTROL_MODE:"):
                mode = status.split(":", 1)[1]
                events.append({"type": "CONTROL_MODE", "mode": mode})
            elif status.startswith("CAMERA_ERROR:"):
                msg = status.split(":", 1)[1]
                self.system_status = f"Camera: {msg}"
                self.append_log("CAMERA", msg[:36], "ERROR")
                events.append({"type": "CAMERA_ERROR", "error": msg})
            elif status == "Camera connected":
                self.camera_connected = True
                self.system_status = "Camera: Connected"
                self.append_log("CAMERA", "Optical sensor online", "ONLINE")
                events.append({"type": "CAMERA_CONNECTED"})
            elif status.startswith("Action:"):
                act = status.split(":", 1)[1].strip()
                self.last_action = f"Last action: {act}"
                src = "GESTURE" if "Gesture" in act else "VOICE"
                events.append({"type": "ACTION", "action": act})
            else:
                self.system_status = status
                events.append({"type": "SYSTEM", "status": status})

        while True:
            try:
                ast = self.assistant_queue.get_nowait()
            except queue.Empty:
                break
            kind, _, detail = ast.partition(":")
            if kind == "REQUEST":
                self.recognized_text = f"Recognized: {detail}"
                events.append({"type": "RECOGNIZED_TEXT", "text": self.recognized_text})
            elif kind in {"FINAL", "INFO", "DONE"}:
                self.assistant_status = detail
                events.append({"type": "ASSISTANT_STATUS", "status": detail})
            elif kind == "ERROR":
                self.assistant_status = f"Error: {detail}"
                events.append({"type": "ASSISTANT_STATUS", "status": self.assistant_status})

        # Spoken text queue (for browser TTS)
        while True:
            try:
                spk = self.spoken_queue.get_nowait()
                events.append({"type": "SPEAK", "text": spk})
            except queue.Empty:
                break

        return events

    def get_state(self) -> Dict[str, Any]:
        return {
            "mouse_paused": self.paused,
            "camera_connected": self.camera_connected,
            "hands_detected": self.hands_detected,
            "control_mode": self.control_mode,
            "gesture_keys_enabled": self.gesture_keys_enabled,
            "detected_gesture": self.detected_gesture,
            "gesture_action": self.gesture_action,
            "gesture_progress": round(self.gesture_progress, 2),
            "voice_mode": self.voice_mode,
            "voice_busy": self.voice_busy,
            "voice_listening_active": self.voice_listening_active,
            "browser_speaking": self.browser_speaking,
            "voice_status": self.voice_status,
            "recognized_text": self.recognized_text,
            "assistant_status": self.assistant_status,
            "last_action": self.last_action,
            "system_status": self.system_status,
            "calibration": {
                "sensitivity": self.gesture_processor.sensitivity,
                "min_cutoff": getattr(self.gesture_processor.filter_x, "min_cutoff", 0.8),
                "click_cooldown": self.gesture_processor.click_cooldown,
                "gesture_hold_normal": self.hand_gesture_detector.hold_time_normal,
                "gesture_hold_dangerous": self.hand_gesture_detector.hold_time_dangerous,
                "gesture_cooldown": self.hand_gesture_detector.cooldown_seconds,
                "scroll_speed": self.hand_gesture_detector.scroll_speed,
            },
            "audit_logs": self.audit_logs[-50:],
        }
