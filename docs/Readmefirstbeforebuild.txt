This is pure blueprint of the app before building the project,
modifications will be done in the later stage.

Features of the prototype
The key requirement is that the user should be able to operate a computer through two input modes: hand gestures and voice commands.

Module A — Hand gesture control
Computer vision · Real-time tracking
- Move the cursor using finger position.
- Left-click and right-click using gestures.
- Scroll using finger movement.
- Zoom in and out using a pinch gesture.

Module B — Voice command control
Speech recognition · Command interpretation
- "Click", "double click" and "right click".
- "Scroll up" and "scroll down".
- "Zoom in" and "zoom out".
- "Move cursor left" or "move cursor right".
- System commands such as volume and mute.

Module C — Unified control interface
Integration · Safety · User experience
- A live camera preview and gesture indicators.
- Microphone and listening status.
- A command log and application status.
- Emergency pause/resume and a safe exit.

Software Architecture used storage path
"C:\Users\subha\Pictures\Screenshots\Screenshot 2026-10-10 112235.png"

The technology stack I recommend
These are the tools I would choose for a 24-hour build, prioritizing working features and integration time over unnecessary complexity.
Component	      Technology	                                Reason
Primary language	Python 3.11 or a compatible installed version	Rapid prototyping and strong computer-vision ecosystem
Camera processing	OpenCV	                                        Webcam capture and live preview
Hand tracking	        MediaPipe	                                Real-time hand landmarks
Numerical processing	NumPy	                                        Distances, coordinate mapping and gesture calculations
Mouse/keyboard	        PyAutoGUI	                                Cross-platform desktop actions with OS-specific limitations
Voice recognition	SpeechRecognition + a working speech backend	Recognize spoken commands
Microphone capture	PyAudio, if required by the chosen backend	Capture voice input
Audio feedback	        pyttsx3 (optional)	                        Spoken confirmations without requiring cloud TTS
Desktop interface	CustomTkinter	                                Quick desktop dashboard and controls
Concurrency	        Python threading and queue	                Keep camera, voice and UI responsive
Packaging	        PyInstaller, if time permits	                Deliver a runnable desktop executable
MediaPipe supports real-time hand-landmark and gesture-recognition pipelines in Python.

Project folder structure

AIRCONTROL/
├── main.py
├── config.py
├── requirements.txt
├── README.md
│
├── vision/
│   ├── camera.py
│   ├── hand_tracker.py
│   ├── gesture_recognizer.py
│   └── cursor_controller.py
│
├── voice/
│   ├── microphone.py
│   ├── speech_recognizer.py
│   └── command_parser.py
│
├── core/
│   ├── command_router.py
│   ├── action_executor.py
│   ├── safety_manager.py
│   └── app_state.py
│
├── controls/
│   ├── mouse.py
│   ├── keyboard.py
│   └── system_controls.py
│
├── ui/
│   ├── dashboard.py
│   └── camera_overlay.py
│
└── tests/
    ├── test_gestures.py
    └── test_commands.py