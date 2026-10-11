"""
AirControl — Modern Web Dashboard Launcher
Starts the Python backend and web server, opening the interactive React Bits dashboard.
"""

import sys
import webbrowser
import threading
import time
import uvicorn

def open_browser():
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:8000")

def main():
    print("=" * 60)
    print("  AIRCONTROL — PRECISION DESKTOP CONTROL SYSTEM")
    print("  Starting Modern Web Dashboard with React Bits...")
    print("  Access dashboard at: http://127.0.0.1:8000")
    print("=" * 60)

    # Launch browser automatically
    threading.Thread(target=open_browser, daemon=True).start()

    # Start FastAPI / Uvicorn server
    uvicorn.run("backend.web_server:app", host="127.0.0.1", port=8000, log_level="info")

if __name__ == "__main__":
    main()
