"""
AirControl — Precision Hand Gesture Detector & Keyboard Mapping Engine
Identifies 5-finger extension states, matches exact keyboard shortcut gestures,
and drives continuous scroll and zoom with stability filtering and safety hold-times.
"""

from collections import deque
import math
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


def _landmark_pt(landmark: Any) -> Tuple[float, float, float]:
    """Extract (x, y, z) from MediaPipe Landmark or dict or tuple."""
    if hasattr(landmark, "x") and hasattr(landmark, "y"):
        z = getattr(landmark, "z", 0.0)
        return float(landmark.x), float(landmark.y), float(z)
    if isinstance(landmark, dict):
        return float(landmark.get("x", 0.0)), float(landmark.get("y", 0.0)), float(landmark.get("z", 0.0))
    if isinstance(landmark, (list, tuple)):
        z = float(landmark[2]) if len(landmark) > 2 else 0.0
        return float(landmark[0]), float(landmark[1]), z
    raise ValueError(f"Unsupported landmark type: {type(landmark)}")


def _dist2d(p1: Tuple[float, float, float], p2: Tuple[float, float, float]) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def detect_finger_states(landmarks: Any, handedness: str = "Right") -> Dict[str, bool]:
    """
    Evaluates whether each of the 5 fingers is extended or folded.
    Uses robust palm-to-thumb geometry and relative joint distances.
    Returns:
        {"thumb": bool, "index": bool, "middle": bool, "ring": bool, "pinky": bool}
    """
    if landmarks is None or len(landmarks) < 21:
        return {f: False for f in ("thumb", "index", "middle", "ring", "pinky")}

    pts = [_landmark_pt(landmarks[i]) for i in range(21)]

    wrist = pts[0]
    thumb_cmc, thumb_mcp, thumb_ip, thumb_tip = pts[1], pts[2], pts[3], pts[4]
    index_mcp, index_pip, index_dip, index_tip = pts[5], pts[6], pts[7], pts[8]
    middle_mcp, middle_pip, middle_dip, middle_tip = pts[9], pts[10], pts[11], pts[12]
    ring_mcp, ring_pip, ring_dip, ring_tip = pts[13], pts[14], pts[15], pts[16]
    pinky_mcp, pinky_pip, pinky_dip, pinky_tip = pts[17], pts[18], pts[19], pts[20]

    palm_width = _dist2d(index_mcp, pinky_mcp)
    if palm_width < 1e-4:
        palm_width = 0.1

    # 1. Four fingers (Index, Middle, Ring, Pinky)
    def is_finger_extended(tip, pip, mcp) -> bool:
        d_tip_wrist = _dist2d(tip, wrist)
        d_pip_wrist = _dist2d(pip, wrist)
        d_tip_mcp = _dist2d(tip, mcp)
        d_pip_mcp = _dist2d(pip, mcp)
        # Tip must be extended outward away from wrist and MCP
        return (d_tip_wrist > d_pip_wrist * 1.05) and (d_tip_mcp > d_pip_mcp * 1.02)

    index_ext = is_finger_extended(index_tip, index_pip, index_mcp)
    middle_ext = is_finger_extended(middle_tip, middle_pip, middle_mcp)
    ring_ext = is_finger_extended(ring_tip, ring_pip, ring_mcp)
    pinky_ext = is_finger_extended(pinky_tip, pinky_pip, pinky_mcp)

    # 2. Thumb geometry
    # Thumb moves radially. When extended, tip is far from pinky MCP (opposite side of palm)
    # and farther from pinky MCP than the thumb IP joint.
    d_thumb_tip_pinky = _dist2d(thumb_tip, pinky_mcp)
    d_thumb_ip_pinky = _dist2d(thumb_ip, pinky_mcp)
    d_thumb_tip_index = _dist2d(thumb_tip, index_mcp)
    d_thumb_ip_index = _dist2d(thumb_ip, index_mcp)

    # Ratio of thumb extension relative to palm width
    thumb_palm_ratio = d_thumb_tip_pinky / palm_width

    # Thumb is extended if its tip is expanded outward beyond IP joint and well away from palm
    thumb_ext = (
        (d_thumb_tip_pinky > d_thumb_ip_pinky * 1.06)
        and (thumb_palm_ratio > 1.08 or d_thumb_tip_index > d_thumb_ip_index * 1.08)
    )

    return {
        "thumb": bool(thumb_ext),
        "index": bool(index_ext),
        "middle": bool(middle_ext),
        "ring": bool(ring_ext),
        "pinky": bool(pinky_ext),
    }


# Exact specification of the 15 hand gesture shortcuts
KEYBOARD_GESTURES = [
    {
        "id": "thumb_index",
        "name": "Thumb + Index",
        "fingers": frozenset({"thumb", "index"}),
        "action": "Right Arrow",
        "type": "press",
        "keys": ["right"],
        "dangerous": False,
    },
    {
        "id": "thumb_index_pinky",
        "name": "Thumb + Index + Pinky",
        "fingers": frozenset({"thumb", "index", "pinky"}),
        "action": "Left Arrow",
        "type": "press",
        "keys": ["left"],
        "dangerous": False,
    },
    {
        "id": "index_only",
        "name": "Index only",
        "fingers": frozenset({"index"}),
        "action": "Space",
        "type": "press",
        "keys": ["space"],
        "dangerous": False,
    },
    {
        "id": "middle_only",
        "name": "Middle only",
        "fingers": frozenset({"middle"}),
        "action": "'z'",
        "type": "press",
        "keys": ["z"],
        "dangerous": False,
    },
    {
        "id": "thumb_index_middle",
        "name": "Thumb + Index + Middle",
        "fingers": frozenset({"thumb", "index", "middle"}),
        "action": "'m'",
        "type": "press",
        "keys": ["m"],
        "dangerous": False,
    },
    {
        "id": "thumb_only",
        "name": "Thumb only",
        "fingers": frozenset({"thumb"}),
        "action": "Enter",
        "type": "press",
        "keys": ["enter"],
        "dangerous": False,
    },
    {
        "id": "index_middle",
        "name": "Index + Middle",
        "fingers": frozenset({"index", "middle"}),
        "action": "Up Arrow",
        "type": "press",
        "keys": ["up"],
        "dangerous": False,
    },
    {
        "id": "index_pinky",
        "name": "Index + Pinky",
        "fingers": frozenset({"index", "pinky"}),
        "action": "Down Arrow",
        "type": "press",
        "keys": ["down"],
        "dangerous": False,
    },
    {
        "id": "index_middle_ring",
        "name": "Index + Middle + Ring",
        "fingers": frozenset({"index", "middle", "ring"}),
        "action": "Ctrl + F4",
        "type": "hotkey",
        "keys": ["ctrl", "f4"],
        "dangerous": True,  # Closes active tab/doc
    },
    {
        "id": "pinky_only",
        "name": "Pinky only",
        "fingers": frozenset({"pinky"}),
        "action": "Ctrl + T",
        "type": "hotkey",
        "keys": ["ctrl", "t"],
        "dangerous": False,
    },
    {
        "id": "four_no_pinky",
        "name": "Thumb + Index + Middle + Ring",
        "fingers": frozenset({"thumb", "index", "middle", "ring"}),
        "action": "Ctrl + Win + Right",
        "type": "hotkey",
        "keys": ["ctrl", "win", "right"],
        "dangerous": True,  # Desktop switch
    },
    {
        "id": "four_no_thumb",
        "name": "Index + Middle + Ring + Pinky",
        "fingers": frozenset({"index", "middle", "ring", "pinky"}),
        "action": "Ctrl + Alt + W",
        "type": "hotkey",
        "keys": ["ctrl", "alt", "w"],
        "dangerous": True,
    },
    {
        "id": "thumb_middle_ring_pinky",
        "name": "Thumb + Middle + Ring + Pinky",
        "fingers": frozenset({"thumb", "middle", "ring", "pinky"}),
        "action": "Esc",
        "type": "press",
        "keys": ["escape"],
        "dangerous": False,
    },
    {
        "id": "thumb_pinky",
        "name": "Thumb + Pinky",
        "fingers": frozenset({"thumb", "pinky"}),
        "action": "F5",
        "type": "press",
        "keys": ["f5"],
        "dangerous": False,
    },
    {
        "id": "thumb_middle_pinky",
        "name": "Thumb + Middle + Pinky",
        "fingers": frozenset({"thumb", "middle", "pinky"}),
        "action": "Mouse Right-Click",
        "type": "right_click",
        "keys": [],
        "dangerous": False,
    },
]

# Continuous gesture definitions (unused shapes)
SHAPE_OPEN_PALM = frozenset({"thumb", "index", "middle", "ring", "pinky"})
SHAPE_FIST = frozenset()


class HandGestureDetector:
    """
    Tracks hand shapes, manages gesture stability with configurable hold times,
    triggers keyboard/mouse shortcuts, and executes continuous scroll & zoom.
    """

    def __init__(
        self,
        hold_time_normal: float = 0.40,
        hold_time_dangerous: float = 0.80,
        cooldown_seconds: float = 0.90,
        scroll_speed: int = 180,
        zoom_step: float = 1.0,
        action_executor: Optional[Callable[[str, List[str]], None]] = None,
    ):
        self.hold_time_normal = float(hold_time_normal)
        self.hold_time_dangerous = float(hold_time_dangerous)
        self.cooldown_seconds = float(cooldown_seconds)
        self.scroll_speed = int(scroll_speed)
        self.zoom_step = float(zoom_step)
        self.action_executor = action_executor

        # Gesture mapping table lookup by exact frozenset
        self.gesture_map: Dict[frozenset, Dict[str, Any]] = {
            g["fingers"]: g for g in KEYBOARD_GESTURES
        }

        # Stability buffer
        self.history: deque = deque(maxlen=10)
        self.candidate_fingers: Optional[frozenset] = None
        self.candidate_start_time: float = 0.0
        self.candidate_gesture: Optional[Dict[str, Any]] = None

        # Cooldown tracker per gesture ID
        self.last_triggered: Dict[str, float] = {}
        self.has_fired_for_current_hold: bool = False

        # Continuous tracking state
        self.continuous_anchor_y: Optional[float] = None
        self.last_continuous_action_time: float = 0.0

        # Telemetry
        self.detected_name: str = "None"
        self.detected_action: str = "None"
        self.progress: float = 0.0

    def reset(self):
        """Reset history and candidate hold state."""
        self.history.clear()
        self.candidate_fingers = None
        self.candidate_start_time = 0.0
        self.candidate_gesture = None
        self.has_fired_for_current_hold = False
        self.continuous_anchor_y = None
        self.detected_name = "None"
        self.detected_action = "None"
        self.progress = 0.0

    def process_landmarks(
        self,
        landmarks: Any,
        handedness: str = "Right",
        now: Optional[float] = None,
    ) -> Tuple[Optional[str], Optional[str], float, Optional[Dict[str, Any]]]:
        """
        Processes hand landmarks for one frame.
        Returns:
            (detected_name, detected_action, progress, triggered_action_dict_or_None)
        """
        if now is None:
            now = time.monotonic()

        if landmarks is None or len(landmarks) < 21:
            self.reset()
            return None, None, 0.0, None

        # 1. Detect extended finger states
        finger_dict = detect_finger_states(landmarks, handedness=handedness)
        extended_set = frozenset(k for k, v in finger_dict.items() if v)
        self.history.append(extended_set)

        # 2. Majority vote across the window
        counts: Dict[frozenset, int] = {}
        for s in self.history:
            counts[s] = counts.get(s, 0) + 1
        most_common = max(counts.items(), key=lambda item: item[1])[0]

        # Require agreement in window
        threshold = 1 if len(self.history) <= 2 else max(2, int(len(self.history) * 0.6))
        if counts[most_common] < threshold:
            self.progress = 0.0
            return self.detected_name, self.detected_action, 0.0, None

        # 3. Handle Continuous Scroll (Open Palm) and Continuous Zoom (Fist)
        pts = [_landmark_pt(landmarks[i]) for i in range(21)]
        hand_y = pts[0][1]  # wrist y

        if most_common == SHAPE_OPEN_PALM:
            self.candidate_gesture = None
            self.candidate_fingers = SHAPE_OPEN_PALM
            self.detected_name = "Open Palm (5 fingers)"
            self.detected_action = "Continuous Scroll"
            self.progress = 1.0

            if self.continuous_anchor_y is None:
                self.continuous_anchor_y = hand_y

            delta = self.continuous_anchor_y - hand_y  # Hand up in camera -> positive delta
            deadband = 0.035
            triggered_cont = None

            if abs(delta) > deadband and (now - self.last_continuous_action_time >= 0.06):
                self.last_continuous_action_time = now
                direction = "up" if delta > 0 else "down"
                scroll_delta = int(self.scroll_speed * (delta / 0.12))
                triggered_cont = {
                    "type": "scroll",
                    "delta": scroll_delta,
                    "direction": direction,
                    "action_label": f"Continuous Scroll ({direction.title()})",
                }
                if self.action_executor:
                    self.action_executor("scroll", [str(scroll_delta)])

            return self.detected_name, self.detected_action, 1.0, triggered_cont

        elif most_common == SHAPE_FIST:
            self.candidate_gesture = None
            self.candidate_fingers = SHAPE_FIST
            self.detected_name = "Fist (0 fingers)"
            self.detected_action = "Continuous Zoom"
            self.progress = 1.0

            if self.continuous_anchor_y is None:
                self.continuous_anchor_y = hand_y

            delta = self.continuous_anchor_y - hand_y
            deadband = 0.045
            triggered_cont = None

            if abs(delta) > deadband and (now - self.last_continuous_action_time >= 0.25):
                self.last_continuous_action_time = now
                direction = "in" if delta > 0 else "out"
                triggered_cont = {
                    "type": "zoom",
                    "direction": direction,
                    "action_label": f"Continuous Zoom ({direction.title()})",
                }
                if self.action_executor:
                    self.action_executor("zoom", [direction])

            return self.detected_name, self.detected_action, 1.0, triggered_cont

        else:
            self.continuous_anchor_y = None

        # 4. Discrete Keyboard Shortcuts (Exact Match from Table)
        gesture = self.gesture_map.get(most_common)
        if gesture is None:
            self.candidate_fingers = None
            self.candidate_gesture = None
            self.detected_name = "None"
            self.detected_action = "None"
            self.progress = 0.0
            self.has_fired_for_current_hold = False
            return "None", "None", 0.0, None

        # Candidate matched
        if self.candidate_fingers != most_common:
            self.candidate_fingers = most_common
            self.candidate_start_time = now
            self.candidate_gesture = gesture
            self.has_fired_for_current_hold = False

        self.detected_name = gesture["name"]
        self.detected_action = gesture["action"]

        required_hold = (
            self.hold_time_dangerous if gesture.get("dangerous", False) else self.hold_time_normal
        )
        elapsed = now - self.candidate_start_time
        self.progress = max(0.0, min(1.0, elapsed / required_hold))

        triggered = None
        if (self.progress >= 0.999 or elapsed >= required_hold - 1e-4) and not self.has_fired_for_current_hold:
            gid = gesture["id"]
            last_fire = self.last_triggered.get(gid, 0.0)
            if now - last_fire >= self.cooldown_seconds:
                self.last_triggered[gid] = now
                self.has_fired_for_current_hold = True
                triggered = dict(gesture)
                if self.action_executor:
                    self.action_executor(gesture["type"], gesture["keys"])

        return self.detected_name, self.detected_action, self.progress, triggered
