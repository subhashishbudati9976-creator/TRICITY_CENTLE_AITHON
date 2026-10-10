# AirControl — Technology Stack Specification

This document provides a comprehensive technical breakdown of every library, runtime, framework, and hardware abstraction layer utilized in **AirControl**. Each technology is analyzed according to its role, codebase location, design rationale, and interaction patterns with other subsystems.

---

## 1. Technology Matrix

| Technology / Library | Version / Runtime | Core Role in AirControl | Codebase Location | Selection Rationale | Subsystem Interactions |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Python** | `3.11.x` | Core application runtime & glue logic | Entire repository (`main.py`, `voice/`, `tests/`) | High-level concurrency primitives, rich ecosystem for CV and audio, rapid prototyping | Orchestrates threads, queues, CV pipelines, speech models, and OS automation |
| **OpenCV (`cv2`)** | `opencv-python >= 4.8` | Camera frame acquisition & image preprocessing | `main.py` (`_camera_worker`) | Low-latency DirectShow hardware access, real-time matrix transformations | Captures webcam feed, flips frames, converts BGR to RGB for MediaPipe and PIL |
| **MediaPipe** | `mediapipe >= 0.10` | 21 3D hand landmark detection & tracking | `main.py` (`_camera_worker`) | State-of-the-art real-time on-device ML pipeline with sub-millisecond inference | Ingests RGB frames from OpenCV; outputs normalized landmarks (tips, wrist, MCP) |
| **SpeechRecognition** | `SpeechRecognition >= 3.10` | Audio stream capture & recognition abstraction | `voice/voice_controller.py` | Unified API for microphone capture, energy calibration, and multi-backend speech dispatch | Wraps PyAudio streams; handles energy thresholding; dispatches to Google or raw PCM |
| **Google Speech Recognition** | Web API (`recognize_google`) | High-accuracy online speech-to-text | `voice/voice_controller.py` (`listen_once`) | Zero-configuration cloud recognition with broad acoustic vocabulary | Receives processed audio bytes; returns transcription string or raises network/unclear exceptions |
| **Vosk** | `vosk >= 0.3.45` | Offline, zero-latency local speech-to-text | `voice/voice_controller.py` (`_load_vosk_model`) | Complete offline privacy, Kaldi-based lightweight acoustic/language model (~50MB) | Consumes raw 16kHz mono PCM byte streams; returns JSON-encoded transcription |
| **PyAudio** | `PyAudio >= 0.2.13` | PortAudio hardware microphone abstraction | Underlying dependency of `speech_recognition` | Low-level cross-platform audio input buffer streaming | Interfaces with Windows Core Audio / MME hardware drivers for microphone capture |
| **PyAutoGUI** | `pyautogui >= 0.9.54` | OS-level input synthesis (mouse & keyboard) | `main.py` (`_mouse_worker`, `_execute_voice_command`) | Simple cross-platform desktop automation with built-in emergency fail-safe | Consumes normalized coordinates and allowlisted voice commands to drive OS cursor and key events |
| **CustomTkinter** | `customtkinter >= 5.2` | Modern, hardware-accelerated dark UI dashboard | `main.py` (`AirControlApp`, `_build_ui`) | Modern styling over standard Tkinter without heavy external GUI runtimes | Drives UI thread, status cards, mode toggles, buttons, and embeds live PIL video frames |
| **Pillow (PIL)** | Underlying CTk / Tk dependency | Image format conversion for Tkinter canvas | `main.py` (`_update_dashboard`) | High-speed memory buffer conversion from NumPy RGB arrays to Tk PhotoImage | Converts OpenCV RGB frames to `ImageTk.PhotoImage` for rendering in `CTkLabel` |
| **NumPy** | `numpy >= 1.24` | Multidimensional array operations for image buffers | Underlying OpenCV / MediaPipe dependency | Standardized C-speed buffer memory layout | Represents raw video frames and landmark tensors |
| **Standard Library (`threading`, `queue`)** | Python Standard Library | Concurrency, decoupled worker loops, thread-safe IPC | `main.py` | Eliminates UI freezing by decoupling I/O-bound audio and CPU-bound vision into daemon threads | Connects `_camera_worker`, `_mouse_worker`, `_voice_worker`, and UI event loop |
| **Pytest & Unittest** | `pytest >= 9.0` | Automated unit testing & regression verification | `tests/` (`test_commands.py`, `test_voice.py`, `test_decoupling.py`) | Deterministic mock validation of hardware logic without requiring physical sensors | Validates normalization, safety allowlist, state decoupling, and error branches |

---

## 2. In-Depth Component Analysis

### 2.1 Python (`3.11+`)
- **Role:** The primary programming language and runtime coordinator.
- **Why Selected:** AirControl requires real-time coordination of disparate computing disciplines: computer vision, acoustic processing, digital signal processing, GUI rendering, and operating system input synthesis. Python provides C-backed bindings for all these domains while allowing clean, thread-safe queue communication in under 500 lines of application code.
- **Architectural Placement:** Runs the top-level event loop and initializes background daemon threads (`_camera_worker`, `_mouse_worker`, `_voice_worker`).

### 2.2 OpenCV (`cv2`)
- **Role:** Camera initialization, video frame capture, frame mirroring, and visual annotation.
- **Implementation Detail in AirControl:**
  ```python
  # Resilient hardware acquisition using Windows DirectShow backend first
  cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
  if not cap.isOpened():
      cap = cv2.VideoCapture(0)
  ```
- **Frame Processing:**
  - Sets resolution to 640x480 at 30 FPS (`CAP_PROP_FRAME_WIDTH`, `CAP_PROP_FRAME_HEIGHT`).
  - Mirrors frames horizontally (`cv2.flip(frame, 1)`) so user hand movements match mirror-reflection intuition.
  - Converts color spaces: `cv2.COLOR_BGR2RGB` for MediaPipe inference and Pillow rendering.
  - Draws visual overlays: landmark connection skeletons via `mp.solutions.drawing_utils.draw_landmarks` and bounding status indicators (`cv2.putText` displaying "PINCH" or "OPEN").
- **Fault Recovery:** Detects dropped frames via `consecutive_drops` counter. At 10 dropped frames, reports status to UI; at 25 dropped frames, releases hardware handle and attempts clean re-initialization.

### 2.3 MediaPipe Hands
- **Role:** ML-based real-time 3D hand landmark detection and tracking.
- **Implementation Detail:**
  ```python
  with hands_module.Hands(
      static_image_mode=False,
      max_num_hands=2,
      min_detection_confidence=0.6,
      min_tracking_confidence=0.6,
  ) as hands:
      result = hands.process(rgb)
  ```
- **Why Selected:** MediaPipe uses a two-stage machine learning pipeline (palm detector followed by a 21-landmark hand model) running on CPU with minimal latency. This leaves CPU headroom for audio processing and GUI rendering on standard laptops.
- **Key Landmarks Utilized:**
  - **Landmark 8 (`INDEX_FINGER_TIP`):** Target coordinates for mouse cursor mapping.
  - **Landmark 4 (`THUMB_TIP`):** Measured against index tip for pinch gesture distance.
  - **Landmark 0 (`WRIST`) & Landmark 9 (`MIDDLE_FINGER_MCP`):** Vector distance provides dynamic palm size normalization, making gesture detection invariant to hand distance from the webcam.

### 2.4 SpeechRecognition & PyAudio
- **Role:** Audio ingestion, ambient noise calibration, and speech-to-text dispatch.
- **Threshold Configuration:**
  ```python
  self.recognizer.dynamic_energy_threshold = True
  self.recognizer.energy_threshold = 300
  self.recognizer.pause_threshold = 0.8
  self.recognizer.phrase_threshold = 0.1
  self.recognizer.non_speaking_duration = 0.3
  ```
- **Acoustic Noise Management:**
  - Ambient noise calibration is performed once upon first microphone access (`duration=0.2s`), preventing repeated blocking delays.
  - Energy threshold is clamped strictly between `80` and `1000` to prevent the recognizer from becoming deaf if transient room noises or speech occur during calibration.

### 2.5 Google Speech Recognition (Online Path)
- **Role:** Cloud-backed speech-to-text provider for broad acoustic models and high conversational accuracy.
- **Implementation Detail:** Calls `recognizer.recognize_google(audio)`.
- **Failure Boundaries:**
  - `sr.UnknownValueError`: Handled with a controlled 1-retry loop ("Speech unclear. Listening again..."). If still unintelligible, safely returns user feedback without crashing.
  - `sr.RequestError`: Caught and surfaced as a connectivity error advising user to switch to Offline mode.

### 2.6 Vosk (Offline Path)
- **Role:** 100% offline, local neural speech-to-text processing.
- **Model Used:** `vosk-model-en-us-0.22-lgraph` (stored in `models/`).
- **Processing Flow:**
  1. Validates model directory existence prior to opening microphone.
  2. Lazily loads `vosk.Model` into memory once.
  3. Extracts raw 16kHz, 16-bit mono PCM bytes:
     ```python
     pcm_data = audio.get_raw_data(convert_rate=16000, convert_width=2)
     ```
  4. Feeds stream into `KaldiRecognizer(model, 16000)`.
  5. Parses JSON output: `json.loads(vosk_recognizer.FinalResult())["text"]`.
- **Trade-offs:** Zero network dependency, total data privacy, but requires local model storage (~50MB) and specific phonetic articulation.

### 2.7 PyAutoGUI
- **Role:** Desktop automation and operating system input emulation.
- **Safety Configurations:**
  ```python
  pyautogui.FAILSAFE = True  # Slamming cursor to (0,0) throws FailSafeException
  pyautogui.PAUSE = 0.01     # Minimal delay between actions
  ```
- **Actions Executed:**
  - `moveTo(x, y)`: Continuous absolute screen cursor movement.
  - `click()`, `doubleClick()`, `rightClick()`: Mouse button triggers.
  - `scroll(200)`, `scroll(-200)`: Vertical viewport scrolling.
  - `hotkey('ctrl', '+')`, `hotkey('ctrl', '-')`: Viewport magnification.
  - `press('volumeup')`, `press('volumedown')`, `press('volumemute')`: Multimedia audio control.
  - `move(dx, dy)`: Relative directional cursor nudging.

### 2.8 CustomTkinter
- **Role:** High-DPI modern graphical dashboard and user feedback center.
- **Key Elements:**
  - Dark-mode aesthetic (`set_appearance_mode("dark")`) with blue accenting.
  - Responsive layout using `grid` weights and segmented control buttons.
  - Decoupled from worker loops via Tkinter's `self.after(20, self._update_dashboard)` poller running at ~50Hz.
  - Real-time video frame rendering inside `CTkLabel` using PIL `ImageTk.PhotoImage`.

### 2.9 Threading and Inter-Process Communication (IPC) Queues
- **Role:** Ensuring a jitter-free 60 FPS user interface while running blocking camera I/O, speech recognition, and OS input synthesis.
- **Queue Architecture:**
  - `frame_queue` (`maxsize=1`): Transports the latest annotated video frame from camera thread to UI thread. Stale frames are dropped immediately (`put_nowait` with catch `queue.Full`).
  - `control_queue` (`maxsize=1`): Transports raw hand tracking coordinates `(x, y, pinching)` to mouse worker. Stale coordinates are dropped immediately to eliminate cursor lag.
  - `command_queue` (`unbounded`): Transports recognized voice command strings to mouse worker.
  - `status_queue` (`unbounded`): Transports human-readable system messages, errors, and action events to UI dashboard.
