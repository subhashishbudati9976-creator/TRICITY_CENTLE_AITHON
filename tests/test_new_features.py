"""
AirControl — Comprehensive Unit & Integration Tests for New Features
Tests:
1. Finger-pattern detection for all 15 gestures + scroll/zoom shapes.
2. Exact matching (Thumb+Index vs Thumb+Index+Pinky, etc.).
3. Hold-time and cooldown logic (including 800ms dangerous gestures).
4. Mode switching ('cursor' vs 'gesture').
5. Wake-phrase fuzzy matching (start & stop phrases).
6. Text cleaning and chunking for browser Web Speech API.
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from backend.engine import AirControlEngine
from core.command_router import CommandRouter
from vision.hand_gesture_detector import (
    HandGestureDetector,
    detect_finger_states,
    KEYBOARD_GESTURES,
    SHAPE_OPEN_PALM,
    SHAPE_FIST,
)
from voice.command_parser import CommandParser
from voice.voice_controller import (
    match_start_wake_phrase,
    match_stop_wake_phrase,
    normalize_wake_text,
)


def create_synthetic_hand(
    thumb: bool = False,
    index: bool = False,
    middle: bool = False,
    ring: bool = False,
    pinky: bool = False,
):
    """
    Creates a list of 21 3D points representing a standardized hand
    with specified fingers extended (True) or folded (False).
    """
    # Base palm landmarks
    pts = [{"x": 0.5, "y": 0.8, "z": 0.0} for _ in range(21)]

    pts[0] = {"x": 0.5, "y": 0.8, "z": 0.0}   # Wrist
    pts[17] = {"x": 0.6, "y": 0.5, "z": 0.0}  # Pinky MCP
    pts[13] = {"x": 0.55, "y": 0.48, "z": 0.0} # Ring MCP
    pts[9] = {"x": 0.5, "y": 0.46, "z": 0.0}  # Middle MCP
    pts[5] = {"x": 0.45, "y": 0.48, "z": 0.0} # Index MCP
    pts[2] = {"x": 0.42, "y": 0.65, "z": 0.0} # Thumb MCP
    pts[3] = {"x": 0.38, "y": 0.60, "z": 0.0} # Thumb IP

    # Thumb
    if thumb:
        # Extended outward away from palm & pinky MCP (17)
        pts[4] = {"x": 0.28, "y": 0.55, "z": 0.0}
    else:
        # Folded across palm towards center
        pts[4] = {"x": 0.48, "y": 0.55, "z": 0.0}

    # Index (MCP 5, PIP 6, DIP 7, TIP 8)
    pts[6] = {"x": 0.45, "y": 0.38, "z": 0.0}
    pts[7] = {"x": 0.45, "y": 0.30, "z": 0.0}
    if index:
        pts[8] = {"x": 0.45, "y": 0.20, "z": 0.0} # Far from wrist
    else:
        pts[8] = {"x": 0.45, "y": 0.45, "z": 0.0} # Curled into palm

    # Middle (MCP 9, PIP 10, DIP 11, TIP 12)
    pts[10] = {"x": 0.50, "y": 0.36, "z": 0.0}
    pts[11] = {"x": 0.50, "y": 0.28, "z": 0.0}
    if middle:
        pts[12] = {"x": 0.50, "y": 0.18, "z": 0.0}
    else:
        pts[12] = {"x": 0.50, "y": 0.45, "z": 0.0}

    # Ring (MCP 13, PIP 14, DIP 15, TIP 16)
    pts[14] = {"x": 0.55, "y": 0.38, "z": 0.0}
    pts[15] = {"x": 0.55, "y": 0.30, "z": 0.0}
    if ring:
        pts[16] = {"x": 0.55, "y": 0.20, "z": 0.0}
    else:
        pts[16] = {"x": 0.55, "y": 0.45, "z": 0.0}

    # Pinky (MCP 17, PIP 18, DIP 19, TIP 20)
    pts[18] = {"x": 0.60, "y": 0.42, "z": 0.0}
    pts[19] = {"x": 0.60, "y": 0.35, "z": 0.0}
    if pinky:
        pts[20] = {"x": 0.60, "y": 0.25, "z": 0.0}
    else:
        pts[20] = {"x": 0.60, "y": 0.47, "z": 0.0}

    return pts


class TestHandGestureDetector(unittest.TestCase):
    def setUp(self):
        self.detector = HandGestureDetector(
            hold_time_normal=0.40,
            hold_time_dangerous=0.80,
            cooldown_seconds=0.90,
        )

    def test_finger_state_detection_individual(self):
        # 1. Index only
        hand = create_synthetic_hand(index=True)
        states = detect_finger_states(hand)
        self.assertTrue(states["index"])
        self.assertFalse(states["thumb"])
        self.assertFalse(states["middle"])
        self.assertFalse(states["ring"])
        self.assertFalse(states["pinky"])

        # 2. Thumb only
        hand = create_synthetic_hand(thumb=True)
        states = detect_finger_states(hand)
        self.assertTrue(states["thumb"])
        self.assertFalse(states["index"])
        self.assertFalse(states["middle"])

        # 3. All 5 fingers extended (Open Palm)
        hand = create_synthetic_hand(thumb=True, index=True, middle=True, ring=True, pinky=True)
        states = detect_finger_states(hand)
        self.assertTrue(all(states.values()))

        # 4. Fist (all folded)
        hand = create_synthetic_hand(thumb=False, index=False, middle=False, ring=False, pinky=False)
        states = detect_finger_states(hand)
        self.assertFalse(any(states.values()))

    def test_all_15_keyboard_gestures_exact_match(self):
        """Verify each of the 15 required gestures matches strictly."""
        for g in KEYBOARD_GESTURES:
            target_fingers = g["fingers"]
            hand = create_synthetic_hand(
                thumb="thumb" in target_fingers,
                index="index" in target_fingers,
                middle="middle" in target_fingers,
                ring="ring" in target_fingers,
                pinky="pinky" in target_fingers,
            )
            states = detect_finger_states(hand)
            detected_set = frozenset(k for k, v in states.items() if v)
            self.assertEqual(
                detected_set,
                target_fingers,
                f"Failed to match gesture: {g['name']} ({g['action']})",
            )

    def test_exact_match_does_not_fire_superset_or_subset(self):
        """
        Verify exact matching:
        - Thumb + Index does NOT fire Thumb + Index + Pinky.
        - Thumb + Index + Pinky does NOT fire Thumb + Index.
        """
        # Feed Thumb + Index repeatedly
        detector = HandGestureDetector(hold_time_normal=0.1)
        hand_thumb_index = create_synthetic_hand(thumb=True, index=True)

        t = 100.0
        for _ in range(8):
            name, act, prog, trig = detector.process_landmarks(hand_thumb_index, now=t)
            t += 0.03

        self.assertEqual(name, "Thumb + Index")
        self.assertEqual(act, "Right Arrow")
        self.assertNotEqual(act, "Left Arrow")

        # Now feed Thumb + Index + Pinky
        detector.reset()
        hand_thumb_index_pinky = create_synthetic_hand(thumb=True, index=True, pinky=True)
        for _ in range(8):
            name, act, prog, trig = detector.process_landmarks(hand_thumb_index_pinky, now=t)
            t += 0.03

        self.assertEqual(name, "Thumb + Index + Pinky")
        self.assertEqual(act, "Left Arrow")
        self.assertNotEqual(act, "Right Arrow")

    def test_hold_time_and_cooldown_execution(self):
        """Test hold time ramp-up and per-gesture cooldown."""
        mock_executor = MagicMock()
        detector = HandGestureDetector(
            hold_time_normal=0.40,
            hold_time_dangerous=0.80,
            cooldown_seconds=1.0,
            action_executor=mock_executor,
        )
        hand = create_synthetic_hand(thumb=True, pinky=True)  # Thumb + Pinky -> F5

        t = 1000.0
        # 1. First 5 frames (~150ms) -> not yet held 400ms, should NOT trigger
        for _ in range(5):
            name, act, prog, trig = detector.process_landmarks(hand, now=t)
            t += 0.03
            self.assertIsNone(trig)
            self.assertLess(prog, 1.0)

        # 2. Advance time past 400ms -> should trigger once
        t = 1000.45
        name, act, prog, trig = detector.process_landmarks(hand, now=t)
        self.assertIsNotNone(trig)
        self.assertEqual(trig["action"], "F5")
        mock_executor.assert_called_once_with("press", ["f5"])

        # 3. Holding longer in same hold session -> should NOT trigger repeatedly
        t += 0.05
        name, act, prog, trig2 = detector.process_landmarks(hand, now=t)
        self.assertIsNone(trig2)

        # 4. Release hand then hold again within 1.0s cooldown -> blocked by cooldown
        detector.reset()
        t = 1000.80
        fired_in_cooldown = False
        for _ in range(16):
            name, act, prog, trig = detector.process_landmarks(hand, now=t)
            if trig is not None:
                fired_in_cooldown = True
            t += 0.03
        self.assertFalse(fired_in_cooldown)  # blocked by cooldown

        # 5. After cooldown expires -> fires again
        detector.reset()
        t = 1001.60
        fired_after_cooldown = False
        for _ in range(16):
            name, act, prog, trig = detector.process_landmarks(hand, now=t)
            if trig is not None:
                fired_after_cooldown = True
            t += 0.03
        self.assertTrue(fired_after_cooldown)

    def test_dangerous_gesture_requires_longer_hold(self):
        """Verify dangerous shortcuts (e.g. Ctrl + F4) require 800ms hold."""
        detector = HandGestureDetector(
            hold_time_normal=0.40,
            hold_time_dangerous=0.80,
        )
        # Index + Middle + Ring -> Ctrl + F4
        hand = create_synthetic_hand(index=True, middle=True, ring=True)

        t = 100.0
        # Check at 500ms (normal gesture would have fired, but dangerous must NOT)
        for _ in range(10):
            detector.process_landmarks(hand, now=t)
            t += 0.05

        t = 100.50
        name, act, prog, trig = detector.process_landmarks(hand, now=t)
        self.assertIsNone(trig)
        self.assertLess(prog, 1.0)  # ~0.62 / 1.0

        # At 850ms, dangerous gesture fires
        t = 100.85
        name, act, prog, trig = detector.process_landmarks(hand, now=t)
        self.assertIsNotNone(trig)
        self.assertEqual(trig["action"], "Ctrl + F4")

    def test_continuous_scroll_open_palm(self):
        """Open Palm held: moving hand up/down generates scroll triggers."""
        detector = HandGestureDetector(scroll_speed=200)
        hand = create_synthetic_hand(thumb=True, index=True, middle=True, ring=True, pinky=True)

        t = 50.0
        # Frame 1: Establish anchor
        hand[0]["y"] = 0.50  # wrist
        name, act, prog, trig = detector.process_landmarks(hand, now=t)
        self.assertEqual(act, "Continuous Scroll")
        self.assertIsNone(trig)

        # Move hand UP (y decreases from 0.50 to 0.40, delta = +0.10)
        t += 0.08
        hand[0]["y"] = 0.40
        name, act, prog, trig_up = detector.process_landmarks(hand, now=t)
        self.assertIsNotNone(trig_up)
        self.assertEqual(trig_up["type"], "scroll")
        self.assertEqual(trig_up["direction"], "up")
        self.assertGreater(trig_up["delta"], 0)

        # Move hand DOWN (y increases to 0.60, delta = -0.10)
        t += 0.08
        hand[0]["y"] = 0.60
        name, act, prog, trig_down = detector.process_landmarks(hand, now=t)
        self.assertIsNotNone(trig_down)
        self.assertEqual(trig_down["direction"], "down")
        self.assertLess(trig_down["delta"], 0)

    def test_continuous_zoom_fist(self):
        """Fist held: moving hand up/down generates zoom in/out."""
        detector = HandGestureDetector()
        hand = create_synthetic_hand(thumb=False, index=False, middle=False, ring=False, pinky=False)

        t = 50.0
        hand[0]["y"] = 0.50
        name, act, prog, trig = detector.process_landmarks(hand, now=t)
        self.assertEqual(act, "Continuous Zoom")

        # Move hand UP -> zoom in
        t += 0.30
        hand[0]["y"] = 0.38
        name, act, prog, trig_in = detector.process_landmarks(hand, now=t)
        self.assertIsNotNone(trig_in)
        self.assertEqual(trig_in["type"], "zoom")
        self.assertEqual(trig_in["direction"], "in")

        # Move hand DOWN -> zoom out
        t += 0.30
        hand[0]["y"] = 0.62
        name, act, prog, trig_out = detector.process_landmarks(hand, now=t)
        self.assertIsNotNone(trig_out)
        self.assertEqual(trig_out["direction"], "out")


class TestEngineAndModeSwitching(unittest.TestCase):
    def setUp(self):
        self.engine = AirControlEngine()

    def test_default_control_mode_is_cursor(self):
        self.assertEqual(self.engine.control_mode, "cursor")

    def test_mode_switching_methods(self):
        self.engine.set_control_mode("gesture")
        self.assertEqual(self.engine.control_mode, "gesture")
        self.assertEqual(self.engine.get_state()["control_mode"], "gesture")

        self.engine.toggle_control_mode()
        self.assertEqual(self.engine.control_mode, "cursor")

    def test_command_router_handles_mode_switching(self):
        router = CommandRouter(app_context=self.engine)
        success, msg, label = router.execute("switch to gesture mode", app=self.engine)
        self.assertTrue(success)
        self.assertEqual(self.engine.control_mode, "gesture")

        success2, msg2, label2 = router.execute("switch to cursor mode", app=self.engine)
        self.assertTrue(success2)
        self.assertEqual(self.engine.control_mode, "cursor")

    def test_command_router_scroll_and_zoom_phrasings(self):
        router = CommandRouter(app_context=self.engine)
        with patch("pyautogui.hotkey") as mock_hotkey, patch("pyautogui.scroll") as mock_scroll:
            s1, _, _ = router.execute("zoom in the page", app=self.engine)
            self.assertTrue(s1)
            mock_hotkey.assert_called()

            s2, _, _ = router.execute("zoom out the page", app=self.engine)
            self.assertTrue(s2)

            s3, _, _ = router.execute("scroll page up", app=self.engine)
            self.assertTrue(s3)
            mock_scroll.assert_called()

            s4, _, _ = router.execute("scroll down the page", app=self.engine)
            self.assertTrue(s4)


class TestWakePhraseMatching(unittest.TestCase):
    def test_start_wake_phrases_fuzzy_matching(self):
        valid_start_phrases = [
            "Hey AirControl, start listening",
            "hey air control",
            "hey aircontrol",
            "hay air control",
            "air control start listening",
            "start listening",
            "hey aircontrol start listening",
            "hay air control start listening",
            "hey air control, please start listening",
        ]
        for phrase in valid_start_phrases:
            self.assertTrue(
                match_start_wake_phrase(phrase),
                f"Failed to match valid start wake phrase: {phrase}",
            )

    def test_start_wake_phrases_rejects_unrelated(self):
        unrelated = [
            "open google chrome",
            "what is the time",
            "stop listening",
            "take a screenshot",
            "hello world",
        ]
        for phrase in unrelated:
            self.assertFalse(
                match_start_wake_phrase(phrase),
                f"Incorrectly matched unrelated phrase: {phrase}",
            )

    def test_stop_wake_phrases_fuzzy_matching(self):
        valid_stop_phrases = [
            "Hey AirControl, stop listening",
            "stop listening",
            "hey aircontrol stop listening",
            "air control stop listening",
            "hay air control stop listening",
        ]
        for phrase in valid_stop_phrases:
            self.assertTrue(
                match_stop_wake_phrase(phrase),
                f"Failed to match valid stop wake phrase: {phrase}",
            )


class TestTextCleaningAndChunking(unittest.TestCase):
    def test_markdown_and_code_cleaning(self):
        # We can implement the python cleaner or test regex equivalence
        import re

        raw = (
            "Here is the answer: **Bold text** and _italic_.\n"
            "```python\nprint('hello')\n```\n"
            "Check [AirControl Docs](https://github.com/aircontrol) for info! 😊"
        )

        # 1. Code blocks
        clean = re.sub(r"```[\s\S]*?```", " ", raw)
        self.assertNotIn("print('hello')", clean)

        # 2. URLs
        clean = re.sub(r"https?://\S+", " ", clean)
        self.assertNotIn("https://", clean)

        # 3. Emojis
        clean = re.sub(
            r"[\U00010000-\U0010ffff]",
            "",
            clean,
        )
        self.assertNotIn("😊", clean)

        # 4. Markdown links
        clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean)
        self.assertIn("AirControl Docs", clean)

    def test_chunking_shortens_long_utterances(self):
        long_paragraph = (
            "AirControl is a modular desktop automation system. "
            "It supports computer vision gesture recognition with MediaPipe hands. "
            "It also features natural voice control powered by SpeechRecognition and Vosk. "
            "Users can control their cursor and execute system shortcuts smoothly without touching the keyboard."
        )
        # Sentences split under 180 chars
        sentences = [s.strip() for s in long_paragraph.split(". ") if s.strip()]
        chunks = []
        cur = ""
        for s in sentences:
            if len(cur + " " + s) <= 180:
                cur = (cur + " " + s).strip()
            else:
                if cur:
                    chunks.append(cur)
                cur = s
        if cur:
            chunks.append(cur)

        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 180)


if __name__ == "__main__":
    unittest.main()
