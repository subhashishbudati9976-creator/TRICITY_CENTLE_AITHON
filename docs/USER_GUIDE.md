# AirControl — User & Operator Guide

A complete, beginner-friendly manual for installing, configuring, operating, and troubleshooting **AirControl** on Windows 10/11.

---

## 1. System Requirements & Prerequisites

Before running AirControl, verify that your machine meets the following requirements:

- **Operating System:** Windows 10 or Windows 11 (64-bit recommended).
- **Python Version:** Python `3.10` or `3.11` (Python 3.11.9 recommended).
- **Webcam:** Any standard USB webcam or integrated laptop camera (minimum 640x480 @ 30 FPS).
- **Microphone:** Built-in laptop microphone or USB headset/external microphone.
- **Network Connection:** Required only for **Online** voice recognition mode. (Offline mode operates entirely without internet).

---

## 2. Installation & Quick Setup

Follow these step-by-step commands in **PowerShell** or **Command Prompt**:

### Step 1: Open the Project Directory
Navigate to the root folder of the AirControl project:
```powershell
cd "c:\CSE Next-Gen Computational Intelligence\Google Antigravity\TRICITY AI-THON\AirControl"
```

### Step 2: Create and Activate a Python Virtual Environment
Creating an isolated virtual environment ensures that system packages do not conflict:
```powershell
# Create the virtual environment
python -m venv .venv

# Activate on Windows PowerShell:
.\.venv\Scripts\Activate.ps1

# (If using standard Command Prompt cmd.exe):
# .\.venv\Scripts\activate.bat
```

> [!NOTE]
> If PowerShell displays an execution policy restriction, run:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process` before activating.

### Step 3: Install Required Dependencies
Install the required packages using the project's `requirements.txt`:
```powershell
pip install -r requirements.txt
```

The installed libraries include:
- `opencv-python` (Camera acquisition & image processing)
- `mediapipe` (Hand landmark tracking)
- `customtkinter` (Modern graphical user interface)
- `pyautogui` (Operating system mouse & keyboard emulation)
- `SpeechRecognition` & `PyAudio` (Microphone capture & audio stream handling)
- `vosk` (Local offline speech recognition)
- `pytest` (Test runner for test verification)

### Step 4: Verify the Offline Vosk Speech Model
AirControl ships with a pre-configured offline model in the `models/` directory:
```
AirControl/
└── models/
    └── vosk-model-en-us-0.22-lgraph/
        ├── am/
        ├── conf/
        ├── graph/
        └── ivector/
```
If you are deploying on a fresh machine where the model is missing:
1. Download `vosk-model-en-us-0.22-lgraph.zip` from [Alphacephei Vosk Models](https://alphacephei.com/vosk/models).
2. Extract the archive into the `AirControl/models/` directory.
3. Confirm that `AirControl/models/vosk-model-en-us-0.22-lgraph` exists with its configuration subfolders.

---

## 3. Launching AirControl

Launch the application using your virtual environment:
```powershell
python main.py
```

The main AirControl dashboard will appear in a modern dark-mode window (`1100x720`).

---

## 4. Understanding the User Interface

```
+---------------------------------------------------------------------------------+
|  AIRCONTROL                           [ Enable Mouse Control ] / [ Pause ... ]  |
+----------------------------------------------------+----------------------------+
|                                                    |       SYSTEM STATUS        |
|                                                    |                            |
|                                                    | Camera: Connected          |
|                                                    | Hands detected: 1          |
|                  LIVE WEBCAM FEED                  | Mouse control: DISABLED    |
|                                                    | Last action: None          |
|             (Mirrored Video Stream with            |                            |
|             Hand Skeleton Overlay & Text)          | Index finger = move cursor |
|                                                    | Pinch = click              |
|                                                    |                            |
|                                                    | -------------------------- |
|                                                    |       VOICE CONTROL        |
|                                                    |     [ Online | Offline ]   |
|                                                    | Voice: Ready               |
|                                                    |   [ Listen for Command ]   |
+----------------------------------------------------+----------------------------+
| Safety: press Pause to disable control. Move mouse to top-left corner for safe stop |
+---------------------------------------------------------------------------------+
```

### Dashboard Elements
1. **Header Bar:**
   - **Title:** "AIRCONTROL"
   - **Pause / Enable Toggle:** Toggles mouse cursor automation on and off. (Starts in **DISABLED** state by default for safety).
2. **Left Panel (Webcam Feed):**
   - Displays real-time mirrored video with visual tracking points and green/white "PINCH" / "OPEN" status.
   - If the webcam is disconnected or in use by another app, clear diagnostic guidance is displayed directly in this area.
3. **Right Panel (Status & Controls):**
   - **Camera Status:** Indicates hardware connection state (`Camera: Connected`, `Reconnecting...`, or error).
   - **Hands Detected:** Live counter showing how many hands are currently in frame (0, 1, or 2).
   - **Mouse Control Status:** Displays whether gesture mouse movement is `ENABLED` or `DISABLED`.
   - **Last Action:** Confirms the most recently executed desktop operation (e.g., `Last action: Click`, `Last action: Zoom In`).
   - **Voice Mode Selector:** Segmented switch between **Online** (Google Cloud STT) and **Offline** (Vosk local engine).
   - **Voice Status:** Displays microphone listening state, transcription text, or errors.
   - **Listen for Command Button:** Initiates microphone capture for one voice phrase.
4. **Bottom Footer:**
   - Displays safety instructions and reminders regarding the PyAutoGUI corner emergency fail-safe.

---

## 5. Operating Hand Gestures

AirControl uses real-time computer vision to track your hand and translate your natural movements into OS cursor actions.

### 5.1 Step 1: Enable Mouse Control
By default, AirControl launches with mouse control paused so that you can position your hand comfortably.
- Click the **"Enable Mouse Control"** button at the top right of the dashboard.
- The button text changes to **"Pause Mouse Control"**, and the status card updates to **"Mouse control: ENABLED"**.

### 5.2 Step 2: Cursor Movement
- Raise your hand in front of the webcam.
- AirControl automatically identifies your **index fingertip** (Landmark 8) as the cursor pointer.
- Move your index finger across the camera view.
- **Coordinate Mapping & Boundaries:** AirControl clips a normalized margin between 8% and 92% of the frame and maps it to your full display resolution.
- **Smoothing:** Cursor positions are smoothed using an exponential filter (`30%` weight on new target coordinates), eliminating natural hand jitter and delivering stable pointer control.

### 5.3 Step 3: Mouse Click (Pinch Gesture)
- Bring the tip of your **thumb** and your **index finger** together in a pinching motion.
- The visual feed will display a bright green **"PINCH"** label.
- A standard **Left Click** is dispatched to your computer at the current cursor position.
- **Pinch Threshold:** AirControl dynamically divides the thumb-to-index distance by your palm size (wrist to middle knuckle). This makes the pinch detection invariant to how close or far your hand is from the camera.
- **Cooldown Mechanism:** A `0.45-second` cooldown prevents rapid unintentional double-clicking during a single pinch.

---

## 6. Operating Voice Commands

AirControl features a complete desktop voice control system that functions **independently of gesture tracking**. Voice commands execute reliably whether mouse control is enabled, paused, or if the webcam is completely offline.

### 6.1 Selecting Recognition Mode
- **Online Mode (Recommended for clear acoustics & internet):** Uses Google Speech Recognition. Provides conversational accuracy and fast cloud inference. Includes automatic 1-retry handling if speech is momentarily unclear.
- **Offline Mode (Recommended for privacy & offline environments):** Uses the local Vosk model. Runs 100% locally on your machine with zero internet traffic.

### 6.2 Triggering a Voice Command
1. Click the **"Listen for Command"** button on the right panel.
2. The button will disable, and the status will display: `Listening (online)...` (or `Listening (offline)...`).
3. Speak one of the supported commands clearly into your microphone.
4. The status updates to `Recognizing...`, displays `Heard: <command>`, and executes the action immediately.
5. The button automatically re-enables and returns to `Voice: Ready`.

### 6.3 Supported Voice Commands Reference

| Category | Spoken Command | Executed Desktop Action |
| :--- | :--- | :--- |
| **Mouse Clicks** | `"click"` or `"left click"` | Executes a standard left mouse click at current cursor position |
| | `"double click"` | Executes a rapid double click |
| | `"right click"` | Opens context menu via right mouse click |
| **Scrolling** | `"scroll up"` | Scrolls current viewport upward by 200 units |
| | `"scroll down"` | Scrolls current viewport downward by 200 units |
| **Zooming** | `"zoom in"` | Sends `Ctrl + +` to zoom into documents, browsers, or editors |
| | `"zoom out"` | Sends `Ctrl + -` to zoom out of viewports |
| **Audio / Volume** | `"volume up"` | Triggers OS multimedia Volume Up key |
| | `"volume down"` | Triggers OS multimedia Volume Down key |
| | `"mute"` or `"unmute"` | Toggles OS multimedia Audio Mute key |
| **Cursor Nudges** | `"move cursor left"` / `"move left"` | Nudges cursor 100 pixels to the left |
| | `"move cursor right"` / `"move right"` | Nudges cursor 100 pixels to the right |
| | `"move cursor up"` / `"move up"` | Nudges cursor 100 pixels upward |
| | `"move cursor down"` / `"move down"` | Nudges cursor 100 pixels downward |
| **Control State** | `"pause control"` or `"pause"` | Temporarily pauses gesture mouse tracking |
| | `"resume control"` or `"resume"` | Resumes gesture mouse tracking |

> [!IMPORTANT]
> **Safety Rejection:** AirControl features a strict command allowlist. If an unrecognized or potentially dangerous command is spoken (e.g., *"delete all files"* or *"open command prompt"*), AirControl logs `Unknown command: <text>` and executes **zero** system actions.

---

## 7. Safety Mechanisms & Fail-Safe

Desktop automation must always prioritize user control and safety. AirControl includes three layers of defense:

1. **Hardware Pause Button:** You can pause mouse tracking at any time by clicking "Pause Mouse Control" or by speaking `"pause"`.
2. **PyAutoGUI Emergency Corner Fail-Safe:** If the cursor behaves unexpectedly or loses tracking, slam your physical mouse into the **top-left corner of your monitor (coordinates 0, 0)**. PyAutoGUI immediately throws a `FailSafeException`. AirControl intercepts this event, disables mouse control automatically, and displays: `Safety stop: mouse control disabled`.
3. **Decoupled Architecture:** Pausing mouse tracking only stops the hand-driven cursor. It does not freeze the application, block video rendering, or disable voice commands.

---

## 8. Troubleshooting & Diagnostics

| Symptom | Probable Cause | Recommended Resolution |
| :--- | :--- | :--- |
| **"Webcam unavailable. Check permissions..."** | Another app (Zoom, Teams, Discord) has exclusive camera access, or camera is unplugged. | Close other video applications. Check Windows Settings -> Privacy & Security -> Camera to ensure desktop apps have access. AirControl will automatically attempt to reconnect. |
| **"Warning: Vosk model missing. Offline mode unavailable."** | Model folder was moved, renamed, or not downloaded. | Check that `models/vosk-model-en-us-0.22-lgraph` exists in the project root. Alternatively, switch to **Online** mode. |
| **"Microphone error: [Errno ...]"** | Windows microphone permission denied or no audio input device connected. | Go to Windows Settings -> System -> Sound -> Input. Verify a default recording device is selected and working. |
| **"No speech detected before timeout"** | The 5-second listening window closed before speech began. | Click **"Listen for Command"** and begin speaking immediately into the microphone. |
| **"Speech was unclear. Please speak clearly..."** | High background noise, or microphone input level is too low. | Reduce ambient noise (fans, background chatter). Speak closer to your microphone at a consistent volume. AirControl will automatically provide one retry attempt. |
| **Cursor feels jittery or unresponsive** | Low ambient lighting causing MediaPipe landmark jitter. | Ensure your hand is well-lit and clearly visible against the background. Keep your hand at least 18 inches away from the webcam. |
| **"Online recognition unavailable: [RequestError]"** | Internet connection dropped while using Online mode. | Switch the segmented button to **Offline** mode to use the local Vosk model without needing internet access. |
