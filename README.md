# AIRCONTROL

> **Touch-Free Multimodal Desktop Interaction via Real-Time Computer Vision and Decoupled Speech Control.**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.8+-5C3EE8?logo=opencv&logoColor=white)](https://opencv.org/)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-Hands_21_Landmarks-007ACC?logo=google&logoColor=white)](https://mediapipe.dev/)
[![Design](https://img.shields.io/badge/Aesthetic-Japanese_Minimal_%C3%97_Swiss_Engineering-20211F)](https://github.com/TomSchimansky/CustomTkinter)
[![Vosk](https://img.shields.io/badge/Offline_STT-Vosk_Kaldi-orange)](https://alphacephei.com/vosk/)
[![Pytest](https://img.shields.io/badge/Tests-48_Passed-brightgreen?logo=pytest&logoColor=white)](https://pytest.org/)
[![OS](https://img.shields.io/badge/Platform-Windows_10%20%2F%2011-0078D6?logo=windows&logoColor=white)](https://www.microsoft.com/windows)

---

## 1. Project Identity & Overview

- **Project Name:** AirControl
- **Tagline:** Touch-Free Multimodal Desktop Interaction via Real-Time Computer Vision and Decoupled Speech Control
- **Visual Direction:** Japanese Minimal × Swiss Engineering (Warm Ivory, Charcoal Ink, Deep Indigo, Vermilion Red, Muted Stone, Soft Sage)
- **Project Category:** Assistive Technology / Human-Computer Interaction (HCI) / Computer Vision
- **Target Audience:** Users with motor or physical mobility limitations, professionals in sterile environments (medical, lab, culinary), presenters, and power users seeking touch-free computing.
- **Primary Objective:** Provide a seamless, robust, and safe alternative to conventional mouse and keyboard peripherals by integrating continuous hand-gesture tracking with discrete, allowlisted voice commands into a single desktop application.

---

## 2. Problem Statement & Proposed Solution

### The Problem
Conventional desktop computing is tethered to physical mice and keyboards. This interaction paradigm presents serious challenges:
- **Accessibility Barriers:** Individuals experiencing motor disabilities, repetitive strain injury (RSI), arthritis, or temporary physical injury face significant strain or outright exclusion.
- **Sterile & Contaminated Environments:** In medical operating rooms, biochemical laboratories, cleanrooms, or even everyday cooking kitchens, touching physical peripherals introduces cross-contamination risks or degrades equipment.
- **Physical Tethering:** Presenters and educators must remain adjacent to their podium to click slides or scroll through reference materials.

### The Proposed Solution
**AirControl** solves this through a unified, multimodal desktop application that combines:
1. **Continuous Visual Input:** Live webcam stream analyzed by MediaPipe to detect 21 3D hand landmarks, smoothed with an adaptive **1€ Filter** (Casiez CHI 2012) and anchored with **Schmitt trigger pinch hysteresis**.
2. **Discrete Voice Control:** Multi-backend speech recognition (Google Cloud STT for online conversational accuracy; local Vosk Kaldi neural model for 100% offline privacy) with a safe **Command Router** executing allowlisted desktop actions, application launches (*Chrome, Notepad, Calculator*), and tab navigations (*LinkedIn, GitHub, YouTube*).
3. **Decoupled Architecture:** Unlike naive systems where voice recognition blocks the camera loop, AirControl's background worker threads and FIFO queues ensure voice commands execute immediately, even when mouse tracking is paused or the webcam is disconnected.

---

## 3. Key Implemented Features

Every feature listed below is verified against the codebase and validated by automated tests:

- [x] **Real-Time Hand Tracking:** 30 FPS landmark tracking using MediaPipe Hands (21 3D points per hand) with horizontal mirror flipping.
- [x] **Adaptive 1€ Filter Smoothing:** Velocity-responsive filtering eliminating jitter when still and eliminating lag during rapid hand sweeps.
- [x] **Schmitt Trigger Pinch Hysteresis:** Dual threshold (`down < 0.28`, `up > 0.35`) eliminating contact chatter and boundary flicker.
- [x] **Click-Freeze Anchor:** 120ms position lock during pinch-down to prevent the physical act of squeezing fingers from shifting the cursor off target.
- [x] **Tracking Loss Grace Hold:** Retains last filtered position across brief occlusions (~130ms) before smoothly clearing state.
- [x] **Application Launching (Allowlist):** Safe voice execution launching Google Chrome, Notepad, and Calculator via argument lists without `shell=True`.
- [x] **Website Tab Navigation:** Voice commands (`"Open LinkedIn in Chrome"`, `"Open GitHub in Chrome"`, `"Open YouTube in Chrome"`) launching or creating tabs in Chrome.
- [x] **Command Deduplication:** 0.6-second debounce preventing accidental double-triggers.
- [x] **Japanese Minimal × Swiss Engineering Interface:** Restrained palette, numbered section labels `[ 01 ]`, monospaced telemetry, and red recording indicator `● REC`.
- [x] **Chronological Telemetry Audit Log:** Real-time instrument readout displaying timestamps, input sources, actions, and execution statuses.
- [x] **Live Parameter Calibration:** Interactive sliders for sensitivity, 1€ filter cutoff, and click debounce.
- [x] **Online Cloud Voice Control:** Google Speech Recognition with an automatic 1-retry mechanism for momentary unclear speech.
- [x] **100% Offline Local Voice Control:** Embedded Vosk Kaldi engine (`vosk-model-en-us-0.22-lgraph`) operating on 16kHz raw PCM audio buffers with zero internet connectivity.
- [x] **Subsystem Decoupling:** Voice control operates independently of camera state or mouse pause toggle.
- [x] **Hardware Pause & PyAutoGUI Fail-Safe:** Dedicated UI button, voice commands (`"pause control"`, `"resume control"`), and emergency corner slam (`(0, 0)`) intercept.

---

## 4. Software Architecture Overview

AirControl separates concern across 5 logical layers connected by thread-safe FIFO queues:

```mermaid
flowchart TD
    User([User])

    subgraph Inputs ["Input Acquisition"]
        Webcam["Webcam (OpenCV DirectShow)"]
        Mic["Microphone (PyAudio / SpeechRecognition)"]
    end

    User -->|Hand Gestures| Webcam
    User -->|Voice Commands| Mic

    subgraph Workers ["Concurrent Background Workers"]
        CamWorker["_camera_worker\nMediaPipe 21 Landmarks\nPinch Ratio < 0.32"]
        VoiceWorker["_voice_worker\nGoogle STT (Online)\nVosk Kaldi (Offline)"]
    end

    Webcam --> CamWorker
    Mic --> VoiceWorker

    subgraph Queues ["Thread-Safe Queues"]
        FrameQ[("frame_queue\nmaxsize=1 (Latest Frame)")]
        ControlQ[("control_queue\nmaxsize=1 (Latest Coordinates)")]
        CommandQ[("command_queue\nUnbounded FIFO (Voice Strings)")]
        StatusQ[("status_queue\nUnbounded FIFO (System Events)")]
    end

    CamWorker -->|Frame| FrameQ
    CamWorker -->|Coordinates| ControlQ
    VoiceWorker -->|Text| CommandQ
    CamWorker -->|Events| StatusQ
    VoiceWorker -->|Events| StatusQ

    subgraph Action ["Action Execution Layer"]
        MouseWorker["_mouse_worker\n1. Drain command_queue\n2. Check Allowlist & Execute\n3. Read control_queue & Smooth\n4. Synthesize OS Input"]
        OS["Windows OS (PyAutoGUI)"]
    end

    CommandQ --> MouseWorker
    ControlQ --> MouseWorker
    MouseWorker --> OS

    subgraph Presentation ["Presentation Layer (Main Thread)"]
        GUI["CustomTkinter Dashboard\n50Hz Poller (after 20ms)\nLive Video + Status Cards"]
    end

    FrameQ --> GUI
    StatusQ --> GUI
```

For the complete architectural specification, refer to [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 5. Technology Stack Summary

| Technology | Role in AirControl | Where Used | Key Advantage |
| :--- | :--- | :--- | :--- |
| **Python 3.11** | Core application language & runtime coordinator | Entire codebase | High-level concurrency primitives; rich ecosystem for CV and audio. |
| **OpenCV (`cv2`)** | Video frame capture, mirroring, preprocessing | `main.py` | DirectShow low-latency hardware access on Windows. |
| **MediaPipe** | 21 3D hand landmark inference | `main.py` | Real-time on-device ML model with sub-millisecond CPU execution. |
| **SpeechRecognition** | Audio capture & cloud STT interface | `voice/voice_controller.py` | Unified microphone streaming with energy threshold calibration. |
| **Google Speech API** | High-accuracy online speech-to-text | `voice/voice_controller.py` | Zero-configuration cloud transcription with controlled 1-retry. |
| **Vosk** | Local, offline speech-to-text | `voice/voice_controller.py` | 100% offline, privacy-first Kaldi neural model (~50MB). |
| **PyAutoGUI** | OS mouse & keyboard automation | `main.py` | Cross-platform desktop input synthesis with emergency fail-safe. |
| **CustomTkinter** | Modern dark-mode user interface | `main.py` | Hardware-accelerated UI rendering without webview bloat. |
| **Pytest** | Automated unit & integration testing | `tests/` | Deterministic verification with hardware mocks. |

For detailed technology analysis, refer to [docs/TECH_STACK.md](docs/TECH_STACK.md).

---

## 6. Project Directory Structure

```
AirControl/
├── .gitignore                      # Git ignore patterns (.venv, models, caches)
├── requirements.txt                # Python package dependencies
├── main.py                         # Application entry point, GUI & worker coordination
├── voice/                          # Speech recognition subsystem
│   ├── __init__.py
│   └── voice_controller.py         # Dual-mode VoiceController (Online + Offline Vosk)
├── models/                         # Neural model storage
│   └── vosk-model-en-us-0.22-lgraph/ # Bundled lightweight Vosk offline model
├── tests/                          # Automated verification test suite
│   ├── __init__.py
│   ├── test_commands.py            # Command normalization, allowlist & safety tests
│   ├── test_decoupling.py          # State decoupling & worker loop tests
│   └── test_voice.py               # Online/offline speech & hardware error tests
├── docs/                           # In-depth technical documentation
│   ├── ARCHITECTURE.md             # Architecture documentation link
│   ├── PRESENTATION_GUIDE.md       # Presentation guide link
│   ├── TECH_STACK.md               # Technology stack deep dive
│   ├── USER_GUIDE.md               # Operator and troubleshooting manual
│   └── TESTING.md                  # Test coverage & verification report
├── ARCHITECTURE.md                 # Complete software architecture specification
├── PRESENTATION.md                 # Hackathon presentation script, pitch & jury Q&A
└── README.md                       # Project root documentation (this file)
```

---

## 7. Supported Gestures and Voice Commands

### Hand Gestures
| Gesture | Trigger Condition | Resulting Desktop Action |
| :--- | :--- | :--- |
| **Point & Move** | Index fingertip (Landmark 8) in camera frame | Moves system mouse cursor with exponential smoothing. |
| **Pinch Click** | Thumb tip to index tip distance ratio `< 0.32` | Dispatches single Left Click at current pointer position (0.45s cooldown). |

### Allowlisted Voice Commands
| Category | Spoken Command | Executed Desktop Action |
| :--- | :--- | :--- |
| **Mouse Clicks** | `"click"` / `"left click"` | Left mouse click |
| | `"double click"` | Double click |
| | `"right click"` | Right mouse click (context menu) |
| **Scrolling** | `"scroll up"` | Scroll viewport up (+200 units) |
| | `"scroll down"` | Scroll viewport down (-200 units) |
| **Zooming** | `"zoom in"` | Zoom in (`Ctrl + +`) |
| | `"zoom out"` | Zoom out (`Ctrl + -`) |
| **Audio** | `"volume up"` | Increase system volume |
| | `"volume down"` | Decrease system volume |
| | `"mute"` / `"unmute"` | Toggle audio mute |
| **Cursor Nudges** | `"move cursor left"` / `"move left"` | Nudge cursor left by 100 pixels |
| | `"move cursor right"` / `"move right"` | Nudge cursor right by 100 pixels |
| | `"move cursor up"` / `"move up"` | Nudge cursor up by 100 pixels |
| | `"move cursor down"` / `"move down"` | Nudge cursor down by 100 pixels |
| **State Control** | `"pause control"` / `"pause"` | Disable gesture mouse tracking |
| | `"resume control"` / `"resume"` | Enable gesture mouse tracking |

> [!NOTE]
> All unrecognized or non-allowlisted phrases are safely rejected with `Unknown command: <text>` and execute **zero** desktop actions.

---

## 8. Installation & Quickstart (Windows)

### Prerequisites
- Windows 10 or 11 (64-bit)
- Python 3.10 or 3.11 installed
- Connected webcam and microphone

### Setup Instructions
```powershell
# 1. Clone repository & navigate to folder
cd "c:\CSE Next-Gen Computational Intelligence\Google Antigravity\TRICITY AI-THON\AirControl"

# 2. Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch AirControl
python main.py
```

For full setup details and troubleshooting, see [docs/USER_GUIDE.md](docs/USER_GUIDE.md).

---

## 9. Testing & Quality Verification

AirControl is validated by **27 automated tests** covering command parsing, offline/online recognition, error propagation, and worker decoupling:

```powershell
# Run the test suite:
.\.venv\Scripts\python -m pytest -v
```

**Verified Test Result:**
```text
======================= 27 passed, 2 warnings in 1.69s ========================
```

For the complete test matrix, mocking strategy, and manual verification procedures, see [docs/TESTING.md](docs/TESTING.md).

---

## 10. Hackathon Presentation & Jury Defense

Preparing for evaluation? Everything you need for judging is prepared in [PRESENTATION.md](PRESENTATION.md):
- **30-Second Elevator Pitch**
- **90-Second Fast Pitch**
- **3-Minute Comprehensive Presentation Script**
- **11-Step Rehearsed Live Demo Plan**
- **14 Anticipated Technical Jury Questions & Answers**
- **Emergency Hardware Fallback Protocols**

---

## 11. Limitations & Future Scope

### Current Limitations:
- **Optical Sensitivity:** MediaPipe requires adequate lighting; low-light or backlit environments can introduce landmark jitter.
- **Push-to-Talk Voice:** Voice commands require clicking "Listen for Command" rather than continuous hands-free wake words.
- **Single-Display Focus:** Coordinate mapping is currently calibrated to the primary monitor resolution.

### Planned Enhancements:
- **Continuous Wake-Word Engine:** Integration of on-device `openWakeWord` (*"Hey AirControl"*) for 100% hands-free voice triggers.
- **Adaptive 1€ Filter:** Replacement of fixed 0.30 exponential smoothing with a velocity-adaptive 1€ filter for jitter-free precision at low speeds and instant response at high speeds.
- **Multi-Gesture Neural Classifier:** Custom lightweight classifier for open palm, fist, peace sign, and swipe gestures.
- **User-Configurable Keybindings:** JSON configuration file to map custom spoken phrases to arbitrary application shortcuts.

---

## 12. Documentation Index

- [ARCHITECTURE.md](ARCHITECTURE.md) — Complete Software Architecture & Concurrency Model
- [PRESENTATION.md](PRESENTATION.md) — Hackathon Presentation Playbook & Jury Defense
- [docs/TECH_STACK.md](docs/TECH_STACK.md) — Technology Stack Analysis & Rationale
- [docs/USER_GUIDE.md](docs/USER_GUIDE.md) — Operator Guide, Setup & Troubleshooting
- [docs/TESTING.md](docs/TESTING.md) — Testing Strategy & Verification Report
