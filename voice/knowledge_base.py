"""Locally grounded answers about capabilities implemented by AirControl."""

from typing import Dict, Optional

from voice.action_registry import capability_descriptions


GESTURES: Dict[str, Dict[str, object]] = {
    "cursor movement": {
        "description": "Move the system cursor with the tracked index fingertip.",
        "instructions": "Enable Mouse Control, keep your hand in camera view, and move your index finger.",
        "parameters": {},
        "actions": ["move cursor"],
        "availability": "implemented",
    },
    "pinch click": {
        "description": "Left-click at the current cursor position by pinching thumb and index fingertips.",
        "instructions": "Enable Mouse Control, bring thumb and index fingertips together, then separate them to re-arm.",
        "parameters": {
            "activation_ratio": 0.28,
            "release_ratio": 0.35,
            "activation_frames": 2,
            "release_frames": 2,
            "click_cooldown_seconds": 0.4,
        },
        "actions": ["left click"],
        "availability": "implemented",
    },
}


def local_answer(question: str) -> Optional[str]:
    """Answer basic capability questions using the live action and gesture registries."""
    normalized = " ".join(question.casefold().replace("-", " ").split())

    asks_a_question = normalized.startswith(
        ("what ", "how ", "which ", "tell me ", "explain ")
    )
    asks_about_gesture = any(
        term in normalized for term in ("gesture", "pinch", "hand tracking")
    )
    if asks_a_question and asks_about_gesture:
        if "right" in normalized and "click" in normalized:
            return (
                "A right-click gesture is not implemented. Say 'right click' to use "
                "AirControl's registered voice action. The implemented hand click is "
                "a thumb-index pinch, which performs a left click."
            )
        supported = "; ".join(
            f"{name}: {item['instructions']}" for name, item in GESTURES.items()
        )
        unsupported = (
            "Other gestures such as gesture-based scrolling, dragging, or opening Start "
            "are not implemented; use the corresponding registered voice action where available."
        )
        return f"Implemented gestures: {supported}. {unsupported}"

    if any(
        phrase in normalized
        for phrase in (
            "what can you do",
            "voice command",
            "capabilit",
            "supported action",
            "what commands",
        )
    ):
        actions = "; ".join(
            capability["description"] for capability in capability_descriptions()
        )
        return (
            "AirControl's registered actions are: "
            f"{actions}. Actions requiring confirmation will ask before execution."
        )

    return None
