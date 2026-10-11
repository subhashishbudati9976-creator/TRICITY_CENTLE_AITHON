"""
AirControl — Modern Web Bridge & Streaming Server
FastAPI + WebSocket server providing MJPEG camera streaming and live bidirectional telemetry.
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Set

# pyrefly: ignore [missing-import]
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from fastapi.responses import JSONResponse, StreamingResponse
# pyrefly: ignore [missing-import]
from fastapi.staticfiles import StaticFiles
# pyrefly: ignore [missing-import]
from pydantic import BaseModel

from backend.engine import AirControlEngine

app = FastAPI(title="AirControl Modern Web Bridge")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = AirControlEngine()
connected_websockets: Set[WebSocket] = set()


class CalibrationPayload(BaseModel):
    sensitivity: float = None
    min_cutoff: float = None
    click_cooldown: float = None


class VoiceModePayload(BaseModel):
    mode: str


@app.on_event("startup")
async def startup_event():
    engine.start()
    asyncio.create_task(broadcast_telemetry_loop())


@app.on_event("shutdown")
def shutdown_event():
    engine.stop()


async def broadcast_telemetry_loop():
    """Polls engine status and logs every 50ms and broadcasts updates to connected WebSockets."""
    last_log_count = len(engine.audit_logs)
    while engine.running:
        try:
            events = engine.drain_events()
            new_logs = []
            current_log_count = len(engine.audit_logs)
            if current_log_count > last_log_count:
                new_logs = engine.audit_logs[last_log_count:]
                last_log_count = current_log_count

            if connected_websockets and (events or new_logs):
                payload = json.dumps({
                    "type": "UPDATE",
                    "state": engine.get_state(),
                    "events": events,
                    "new_logs": new_logs,
                })
                dead_sockets = set()
                for ws in list(connected_websockets):
                    try:
                        await ws.send_text(payload)
                    except Exception:
                        dead_sockets.add(ws)
                connected_websockets.difference_update(dead_sockets)
        except Exception as exc:
            print("Telemetry broadcast error:", exc)
        await asyncio.sleep(0.04)


@app.get("/api/state")
def get_state():
    return JSONResponse(engine.get_state())


@app.post("/api/action/toggle_mouse")
def toggle_mouse():
    paused = engine.toggle_pause()
    return JSONResponse({"mouse_paused": paused})


@app.post("/api/action/listen_voice")
def listen_voice():
    success = engine.start_voice()
    return JSONResponse({"success": success})


@app.post("/api/action/cancel_voice")
def cancel_voice():
    engine.cancel_current_task()
    return JSONResponse({"success": True})


@app.post("/api/action/set_voice_mode")
def set_voice_mode(payload: VoiceModePayload):
    mode = engine.set_voice_mode(payload.mode)
    return JSONResponse({"voice_mode": mode})


@app.post("/api/action/update_calibration")
def update_calibration(payload: CalibrationPayload):
    engine.update_calibration(
        sensitivity=payload.sensitivity,
        min_cutoff=payload.min_cutoff,
        click_cooldown=payload.click_cooldown,
    )
    return JSONResponse({"success": True, "calibration": engine.get_state()["calibration"]})


def generate_mjpeg_stream():
    """Generator for multipart/x-mixed-replace MJPEG streaming."""
    blank_frame = None
    while engine.running:
        frame_bytes = engine.get_latest_jpeg()
        if frame_bytes is None:
            time.sleep(0.04)
            continue
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )
        time.sleep(0.025)


@app.get("/api/stream")
def video_stream():
    return StreamingResponse(
        generate_mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.add(websocket)
    # Send initial state
    await websocket.send_text(json.dumps({
        "type": "INIT_STATE",
        "state": engine.get_state(),
    }))
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            action = msg.get("action")
            if action == "toggle_mouse":
                engine.toggle_pause()
            elif action == "listen_voice":
                engine.start_voice()
            elif action == "cancel_voice":
                engine.cancel_current_task()
            elif action == "set_voice_mode":
                engine.set_voice_mode(msg.get("mode", "online"))
            elif action == "update_calibration":
                engine.update_calibration(**msg.get("settings", {}))
    except WebSocketDisconnect:
        connected_websockets.discard(websocket)
    except Exception:
        connected_websockets.discard(websocket)


# Mount frontend dist static files if built
dist_path = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if dist_path.exists():
    app.mount("/", StaticFiles(directory=str(dist_path), html=True), name="frontend")
