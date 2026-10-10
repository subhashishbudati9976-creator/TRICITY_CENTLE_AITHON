# AirControl — Testing, Verification & Quality Assurance Report

This document details the test architecture, automated verification suite, mocking strategies, and manual quality assurance procedures for **AirControl**.

---

## 1. Automated Test Suite Summary

AirControl includes a comprehensive automated test suite consisting of **27 passing unit and integration tests** built on Python's `unittest` framework and executed with `pytest`.

### 1.1 Test Execution & Verified Results

**Command Executed:**
```powershell
.\.venv\Scripts\python -m pytest -v
```

**Actual Verified Output:**
```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\CSE Next-Gen Computational Intelligence\Google Antigravity\TRICITY AI-THON\AirControl
collected 27 items

tests/test_commands.py::TestCommandExecution::test_click_command_when_paused PASSED [  3%]
tests/test_commands.py::TestCommandExecution::test_double_click_hyphenated PASSED [  7%]
tests/test_commands.py::TestCommandExecution::test_left_click_normalized_punctuation PASSED [ 11%]
tests/test_commands.py::TestCommandExecution::test_move_cursor_by_voice PASSED [ 14%]
tests/test_commands.py::TestCommandExecution::test_pause_and_resume_control PASSED [ 18%]
tests/test_commands.py::TestCommandExecution::test_right_click PASSED    [ 22%]
tests/test_commands.py::TestCommandExecution::test_scroll_up_and_down PASSED [ 25%]
tests/test_commands.py::TestCommandExecution::test_unknown_and_malicious_commands_rejected PASSED [ 29%]
tests/test_commands.py::TestCommandExecution::test_volume_controls_and_mute PASSED [ 33%]
tests/test_commands.py::TestCommandExecution::test_zoom_in_and_out PASSED [ 37%]
tests/test_decoupling.py::TestDecouplingAndWorker::test_dashboard_handles_camera_error_and_reconnection PASSED [ 40%]
tests/test_decoupling.py::TestDecouplingAndWorker::test_dashboard_handles_control_paused_and_resumed PASSED [ 44%]
tests/test_decoupling.py::TestDecouplingAndWorker::test_dashboard_status_preserves_heard_voice_text PASSED [ 48%]
tests/test_decoupling.py::TestDecouplingAndWorker::test_dashboard_status_preserves_voice_error PASSED [ 51%]
tests/test_decoupling.py::TestDecouplingAndWorker::test_dashboard_updates_last_action_on_command PASSED [ 55%]
tests/test_decoupling.py::TestDecouplingAndWorker::test_voice_commands_execute_without_camera_and_when_paused PASSED [ 59%]
tests/test_voice.py::TestVoiceController::test_close_releases_resources PASSED [ 62%]
tests/test_voice.py::TestVoiceController::test_default_model_path_exists PASSED [ 66%]
tests/test_voice.py::TestVoiceController::test_microphone_os_error PASSED [ 70%]
tests/test_voice.py::TestVoiceController::test_microphone_timeout PASSED [ 74%]
tests/test_voice.py::TestVoiceController::test_missing_model_path_handled_gracefully PASSED [ 77%]
tests/test_voice.py::TestVoiceController::test_offline_empty_recognition PASSED [ 81%]
tests/test_voice.py::TestVoiceController::test_offline_recognition_success PASSED [ 85%]
tests/test_voice.py::TestVoiceController::test_online_recognition_success PASSED [ 88%]
tests/test_voice.py::TestVoiceController::test_online_request_error PASSED [ 92%]
tests/test_voice.py::TestVoiceController::test_online_unclear_speech PASSED [ 96%]
tests/test_voice.py::TestVoiceController::test_unintelligible_speech_controlled_retry PASSED [100%]

======================= 27 passed, 2 warnings in 1.69s ========================
```

---

## 2. Test Suites and Coverage Breakdown

### 2.1 Command Normalization & Action Safety (`tests/test_commands.py`)
This suite validates the command processor and desktop execution safety boundary.

| Test Name | Verified Behavior |
| :--- | :--- |
| `test_click_command_when_paused` | Confirms that `"click"` executes `pyautogui.click()` even when gesture tracking is paused (`self.paused = True`). |
| `test_left_click_normalized_punctuation` | Verifies punctuation stripping and capitalization normalization (e.g., `"Left Click."` matches `"left click"`). |
| `test_double_click_hyphenated` | Verifies hyphen replacement (e.g., `"Double-Click!"` normalizes to `"double click"` and calls `pyautogui.doubleClick()`). |
| `test_right_click` | Verifies right click execution via `pyautogui.rightClick()` and updates status queue. |
| `test_scroll_up_and_down` | Verifies vertical scrolling with positive (`200`) and negative (`-200`) offsets. |
| `test_zoom_in_and_out` | Verifies application magnification shortcuts (`Ctrl + +` and `Ctrl + -`) with 50ms interval. |
| `test_volume_controls_and_mute` | Verifies multimedia keys: `"volume up"`, `"volume down"`, and `"mute"` / `"unmute"`. |
| `test_move_cursor_by_voice` | Verifies directional 100px relative cursor nudges (left, right, up, down). |
| `test_pause_and_resume_control` | Verifies that `"pause control"` sets `self.paused = True` and `"resume control"` restores it to `False`. |
| `test_unknown_and_malicious_commands_rejected` | Proves that arbitrary or dangerous phrases (e.g., `"delete all files"`, `"format c:"`, `"powershell rm -rf"`) are rejected without executing OS actions. |

### 2.2 Voice Recognition Controller (`tests/test_voice.py`)
This suite validates speech recognition workflows, Vosk model integration, network fault tolerance, and microphone error handling.

| Test Name | Verified Behavior |
| :--- | :--- |
| `test_default_model_path_exists` | Validates that the bundled Vosk model directory (`models/vosk-model-en-us-0.22-lgraph`) exists on disk. |
| `test_missing_model_path_handled_gracefully` | Confirms that initializing offline mode with a non-existent model path produces an informative error without throwing an unhandled exception or blocking on microphone input. |
| `test_microphone_timeout` | Verifies that when no speech is detected within the listening window, an informative timeout message is returned. |
| `test_microphone_os_error` | Simulates audio hardware failures (`OSError: No default input device`) and verifies clean error propagation. |
| `test_online_recognition_success` | Validates successful Google Speech Recognition transcription flow. |
| `test_online_unclear_speech` | Verifies graceful fallback message when audio cannot be transcribed (`sr.UnknownValueError`). |
| `test_unintelligible_speech_controlled_retry` | Validates the automatic 1-retry mechanism: if initial recognition fails with `sr.UnknownValueError`, a second attempt is triggered before returning an error. |
| `test_online_request_error` | Simulates internet dropouts (`sr.RequestError`) and confirms helpful offline-mode switch recommendations. |
| `test_offline_recognition_success` | Simulates local Vosk Kaldi recognition with raw 16kHz PCM data, validating JSON parsing and text extraction. |
| `test_offline_empty_recognition` | Verifies behavior when Vosk yields an empty string result. |
| `test_close_releases_resources` | Verifies that calling `.close()` resets loaded model handles to free memory. |

### 2.3 Subsystem Decoupling & Concurrency (`tests/test_decoupling.py`)
This suite validates the thread decoupling, IPC queues, and UI dashboard update logic.

| Test Name | Verified Behavior |
| :--- | :--- |
| `test_voice_commands_execute_without_camera_and_when_paused` | Proves that the action worker drains voice commands independently of the camera feed or gesture pause state. |
| `test_dashboard_status_preserves_heard_voice_text` | Ensures that UI status updates do not prematurely overwrite recognized voice text with `"Voice: Ready"`. |
| `test_dashboard_status_preserves_voice_error` | Verifies that voice errors remain visible to the user on the dashboard while re-enabling the listen button. |
| `test_dashboard_handles_control_paused_and_resumed` | Validates dashboard state transitions between enabled and disabled states. |
| `test_dashboard_handles_camera_error_and_reconnection` | Verifies that camera drop and reconnection messages are formatted and displayed properly in the UI. |
| `test_dashboard_updates_last_action_on_command` | Confirms that executed actions update the `last_action_var` display element. |

---

## 3. Mocking Strategy & Deterministic Testing

Testing computer vision, speech recognition, and OS input synthesis on headless machines or developer workstations without physical webcams and microphones requires targeted mocking.

### What is Mocked in Automated Tests:
1. **PyAutoGUI OS Synthesis:**
   - Functions like `pyautogui.click()`, `pyautogui.move()`, and `pyautogui.press()` are patched via `unittest.mock.patch` to verify correct arguments and call counts without moving the developer's physical mouse or triggering unwanted keystrokes.
2. **Microphone Hardware Streams:**
   - `speech_recognition.Microphone` is patched to simulate audio context entrance without requiring a physical soundcard.
   - `adjust_for_ambient_noise` is mocked during unit tests to avoid opening PortAudio streams.
3. **Vosk Kaldi Recognizer:**
   - `vosk.KaldiRecognizer` and `vosk.Model` are patched in `test_voice.py` to return synthetic JSON payloads (`{"text": "scroll down"}`) without waiting for local neural inference.
4. **CustomTkinter GUI Loop:**
   - UI widgets (`CTkLabel`, `StringVar`, `after`) are mocked in `test_decoupling.py` using `unittest.mock.MagicMock`, enabling rapid unit testing of dashboard state logic in milliseconds.

---

## 4. Manual Hardware Verification Checklist

Prior to hackathon judging, run through this step-by-step physical hardware checklist:

- [ ] **1. Camera Initialization:**
  - Launch `python main.py`.
  - Confirm video feed renders within 2 seconds.
  - Verify mirrored perspective (moving right hand moves rightward on screen).
- [ ] **2. Hand Landmark Tracking:**
  - Raise hand in front of camera.
  - Verify that the 21-landmark skeleton appears over hand joints.
  - Confirm "Hands detected: 1" appears in the status panel.
- [ ] **3. Gesture Cursor Movement:**
  - Click "Enable Mouse Control".
  - Move index finger across camera frame.
  - Confirm cursor smoothly tracks fingertip position with jitter suppression.
- [ ] **4. Gesture Click (Pinch):**
  - Bring thumb and index finger together.
  - Verify "PINCH" appears in green text on camera overlay.
  - Confirm a click is registered and "Last action: Click" appears on dashboard.
- [ ] **5. PyAutoGUI Emergency Stop:**
  - Move physical mouse abruptly to top-left screen corner (0, 0).
  - Confirm mouse control is automatically disabled and status indicates "Safety stop: mouse control disabled".
- [ ] **6. Online Voice Control:**
  - Select "Online" mode.
  - Click "Listen for Command".
  - Say `"volume up"`.
  - Confirm OS volume increases and "Last action: Volume Up" appears.
- [ ] **7. Voice Operation while Paused:**
  - Click "Pause Mouse Control" (or verify it is paused).
  - Click "Listen for Command".
  - Say `"double click"`.
  - Confirm double-click is executed even while gesture tracking is paused.
- [ ] **8. Offline Voice Control:**
  - Disconnect Wi-Fi or disable internet.
  - Select "Offline" mode.
  - Click "Listen for Command".
  - Say `"scroll down"`.
  - Confirm active window scrolls downward without internet access.
- [ ] **9. Clean Shutdown:**
  - Close application via window close button (X).
  - Confirm camera light turns off immediately and Python process exits without hanging daemon threads.

---

## 5. Known Coverage Gaps & Future Improvements

1. **End-to-End Latency Benchmarking:**
   - Automated tests verify functional correctness and call counts; they do not measure hardware frame-to-cursor latency in milliseconds.
2. **Visual Lighting Variation Testing:**
   - Automated tests mock MediaPipe inference; testing tracking resilience under low-light or uneven backlighting currently requires manual hardware inspection.
3. **Cross-Platform OS Keystroke Emulation:**
   - Volume control keys (`volumeup`, `volumedown`, `volumemute`) are verified for Windows multimedia keybindings. Linux / macOS X11 keymaps require further platform-specific testing.
