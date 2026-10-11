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
from voice.voice_controller import VoiceController

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.01

SCREEN_W, SCREEN_H = pyautogui.size()


class AirControlEngine:
    def __init__(self):
        self.running = True
        self.paused = True
        self.camera_connected = False
        self.current_action_description = ""

        self.gesture_processor = GestureProcessor(screen_w=SCREEN_W, screen_h=SCREEN_H)
        self.command_router = CommandRouter(
            app_context=self, confirmation_fn=self._action_confirmation
        )
        self.voice_controller = VoiceController()
        self.voice_mode = "online"
        self.voice_busy = False

        self.frame_queue = queue.Queue(maxsize=1)
        self.control_queue = queue.Queue(maxsize=1)
        self.status_queue = queue.Queue()
        self.assistant_queue = queue.Queue()
        self.command_queue = queue.Queue()

        self.task_cancel_event = threading.Event()
        self.task_active_event = threading.Event()

        # Telemetry State
        self.hands_detected = 0
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

    def start(self):
        self.running = True
        self.append_log("SYS", "AirControl Engine Online", "ONLINE")
        self.camera_thread = threading.Thread(target=self._camera_worker, daemon=True)
        self.mouse_thread = threading.Thread(target=self._mouse_worker, daemon=True)
        self.camera_thread.start()
        self.mouse_thread.start()

    def stop(self):
        self.running = False
        self.paused = True
        if self.gesture_processor:
            self.gesture_processor.reset()

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
        # For non-blocking web execution, automatically confirm safe registered actions
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
                            frame, f"{'PINCH' if pinching else 'OPEN'} {pinch_ratio:.2f}", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                            (0, 255, 0) if pinching else (255, 255, 255), 2,
                        )
                        self._publish_control((index_tip.x, index_tip.y, pinching))
                    else:
                        self.gesture_processor.reset_pinch_detection()
                        self._publish_control((None, None, False))

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
                            self.status_queue.put("CONTROL:PAUSED")
                            self.status_queue.put("Safety stop: mouse control disabled")
                        except Exception as exc:
                            self.status_queue.put(f"Command error: {exc}")
                            traceback.print_exc()

                # 2. Process gesture sample
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

            except Exception:
                time.sleep(0.02)

    def _execute_voice_command(self, raw_command: str):
        self.task_active_event.set()
        try:
            self.status_queue.put(f"VOICE_STATUS:Executing: {raw_command}")
            # CommandRouter.execute() returns (success: bool, message: str, label: str)
            success, status_text, _label = self.command_router.execute(
                raw_command, app=self
            )
            if success:
                self.status_queue.put(f"Action: {status_text}")
                self.assistant_queue.put(f"FINAL:{status_text}")
            else:
                self.status_queue.put(f"VOICE_ERROR:{status_text}")
                self.assistant_queue.put(f"ERROR:{status_text}")
        except Exception as exc:
            self.status_queue.put(f"VOICE_ERROR:{exc}")
            self.assistant_queue.put(f"ERROR:{exc}")
        finally:
            self.task_active_event.clear()
            self.voice_busy = False
            self.status_queue.put("VOICE_READY")

    def _voice_worker(self, mode: str):
        try:
            recognized_text, error = self.voice_controller.listen_once(
                mode=mode,
                on_status=lambda msg: self.status_queue.put(f"VOICE_STATUS:{msg}"),
            )
            if error:
                self.status_queue.put(f"VOICE_ERROR:{error}")
                self.voice_busy = False
                self.status_queue.put("VOICE_READY")
            elif recognized_text:
                self.assistant_queue.put(f"REQUEST:{recognized_text}")
                self.status_queue.put(f"Heard: {recognized_text}")
                normalized = " ".join(recognized_text.lower().replace("-", " ").split())
                if normalized in {
                    "cancel task", "cancel current task", "stop current task", "cancel request"
                }:
                    self.task_cancel_event.set()
                    self.assistant_queue.put("FINAL:Cancellation requested by voice.")
                    self.voice_busy = False
                    self.status_queue.put("VOICE_READY")
                elif self.task_cancel_event.is_set():
                    self.assistant_queue.put("FINAL:Voice request cancelled.")
                    self.voice_busy = False
                    self.status_queue.put("VOICE_READY")
                else:
                    self.command_queue.put(recognized_text)
            else:
                self.status_queue.put("VOICE_ERROR:No speech recognized")
                self.voice_busy = False
                self.status_queue.put("VOICE_READY")
        except Exception as exc:
            self.status_queue.put(f"VOICE_ERROR:{exc}")
            self.voice_busy = False
            self.status_queue.put("VOICE_READY")

    def toggle_pause(self) -> bool:
        self.paused = not self.paused
        if self.gesture_processor:
            self.gesture_processor.reset()
        if self.paused:
            self.append_log("CONTROL", "Mouse control paused", "PAUSED")
            self.system_status = "Mouse control paused"
            self.last_action = "Last action: Mouse control paused"
        else:
            self.append_log("CONTROL", "Mouse control active", "ONLINE")
            self.system_status = "Mouse control active"
            self.last_action = "Last action: Mouse control active"
        self._publish_control((None, None, False))
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
        if self.voice_busy or not self.running or self.task_active_event.is_set():
            return False
        self.task_cancel_event.clear()
        self.voice_busy = True
        self.recognized_text = "Listening for a request..."
        self.voice_status = f"Listening ({self.voice_mode})..."
        self.append_log("VOICE", f"Microphone active ({self.voice_mode})", "LISTENING")
        threading.Thread(target=self._voice_worker, args=(self.voice_mode,), daemon=True).start()
        return True

    def cancel_current_task(self):
        if self.task_active_event.is_set() or self.voice_busy:
            self.task_cancel_event.set()
            self.assistant_status = "Cancellation requested."
            self.append_log("TASK", "Task cancelled by user", "CANCEL")
        else:
            self.assistant_status = "No active task to cancel."

    def update_calibration(self, sensitivity: Optional[float] = None, min_cutoff: Optional[float] = None, click_cooldown: Optional[float] = None):
        kwargs = {}
        if sensitivity is not None:
            kwargs["sensitivity"] = float(sensitivity)
        if min_cutoff is not None:
            kwargs["min_cutoff"] = float(min_cutoff)
        if click_cooldown is not None:
            kwargs["click_cooldown"] = float(click_cooldown)
        self.gesture_processor.update_settings(**kwargs)
        self.append_log("CALIB", f"Updated settings: {kwargs}", "CONFIG")

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
                self.append_log("SAFETY", "Mouse control paused", "HOLD")
                events.append({"type": "CONTROL", "paused": True})
            elif status == "CONTROL:RESUMED":
                self.paused = False
                self.append_log("ENGINE", "Mouse control active", "ONLINE")
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
                self.append_log(src, act[:36], "SUCCESS")
                events.append({"type": "ACTION", "action": act})
            else:
                self.system_status = status
                self.append_log("SYSTEM", status[:36], "EVENT")
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

        return events

    def get_state(self) -> Dict[str, Any]:
        return {
            "mouse_paused": self.paused,
            "camera_connected": self.camera_connected,
            "hands_detected": self.hands_detected,
            "voice_mode": self.voice_mode,
            "voice_busy": self.voice_busy,
            "voice_status": self.voice_status,
            "recognized_text": self.recognized_text,
            "assistant_status": self.assistant_status,
            "last_action": self.last_action,
            "system_status": self.system_status,
            "calibration": {
                "sensitivity": self.gesture_processor.sensitivity,
                "min_cutoff": getattr(self.gesture_processor.filter_x, "min_cutoff", 0.8),
                "click_cooldown": self.gesture_processor.click_cooldown,
            },
            "audit_logs": self.audit_logs[-50:],
        }
