import time
import unittest

from vision.gesture_processor import GestureProcessor, OneEuroFilter


class TestGestureProcessor(unittest.TestCase):
    def setUp(self):
        self.processor = GestureProcessor(
            screen_w=1920,
            screen_h=1080,
            sensitivity=1.0,
            min_cutoff=1.0,
            beta=0.01,
            pinch_down_threshold=0.28,
            pinch_up_threshold=0.35,
            click_cooldown=0.40,
            freeze_duration=0.12,
        )

    def test_filter_removes_jitter_on_static_hand(self):
        # Feed jittery stationary coordinates at 60Hz
        t = 1000.0
        dt = 1.0 / 60.0
        center_x = 0.5
        center_y = 0.5
        outputs_x = []

        for i in range(30):
            # Add synthetic high frequency noise (+-0.005)
            jitter = 0.005 if (i % 2 == 0) else -0.005
            sx, sy, click = self.processor.process_frame(
                center_x + jitter, center_y + jitter, False, timestamp=t
            )
            outputs_x.append(sx)
            t += dt

        # Standard deviation or diff in outputs should be heavily damped
        diffs = [abs(outputs_x[i] - outputs_x[i - 1]) for i in range(1, len(outputs_x))]
        avg_diff = sum(diffs) / len(diffs)
        # 0.005 in 1920 screen is ~10 pixels raw jump; filter should keep avg delta very small
        self.assertLess(avg_diff, 5.0)

    def test_filter_adapts_to_fast_movement(self):
        # A fast movement should not lag behind indefinitely
        t = 1000.0
        dt = 0.033
        # Start at 0.2, rapidly move to 0.8 in 3 steps
        self.processor.process_frame(0.2, 0.5, False, timestamp=t)
        t += dt
        sx, sy, _ = self.processor.process_frame(0.8, 0.5, False, timestamp=t)

        target_x, _ = self.processor.map_coordinates(0.8, 0.5)
        # One Euro filter with high beta tracks fast velocity quickly
        # Difference between target_x and sx should be less than 50% after big jump
        self.assertGreater(sx, 1920 * 0.5)

    def test_coordinate_mapping_clamps_and_applies_margin(self):
        # Outside active interaction margin should cleanly clamp without crashing
        x1, y1 = self.processor.map_coordinates(0.01, 0.01)
        x2, y2 = self.processor.map_coordinates(0.99, 0.99)

        self.assertGreaterEqual(x1, 15)
        self.assertGreaterEqual(y1, 15)
        self.assertLessEqual(x2, 1920 - 15)
        self.assertLessEqual(y2, 1080 - 15)

    def test_pinch_hysteresis_schmitt_trigger(self):
        # Hand starts open
        # ratio 0.30: not yet below down_threshold (0.28) -> should remain False
        pinching, r = self.processor.calculate_pinch(
            index_x=0.5, index_y=0.5,
            thumb_x=0.5, thumb_y=0.53,  # dist 0.03
            wrist_x=0.5, wrist_y=0.7,
            middle_mcp_x=0.5, middle_mcp_y=0.6  # palm 0.10 -> ratio 0.30
        )
        self.assertFalse(pinching)

        # ratio 0.25: drops below down_threshold (0.28) -> becomes True
        pinching, r = self.processor.calculate_pinch(
            index_x=0.5, index_y=0.5,
            thumb_x=0.5, thumb_y=0.525,  # dist 0.025 -> ratio 0.25
            wrist_x=0.5, wrist_y=0.7,
            middle_mcp_x=0.5, middle_mcp_y=0.6
        )
        self.assertTrue(pinching)

        # ratio 0.32: relaxes to 0.32, which is between 0.28 and 0.35 -> hysteresis maintains True!
        pinching, r = self.processor.calculate_pinch(
            index_x=0.5, index_y=0.5,
            thumb_x=0.5, thumb_y=0.532,  # dist 0.032 -> ratio 0.32
            wrist_x=0.5, wrist_y=0.7,
            middle_mcp_x=0.5, middle_mcp_y=0.6
        )
        self.assertTrue(pinching)

        # ratio 0.40: relaxes above up_threshold (0.35) -> becomes False!
        pinching, r = self.processor.calculate_pinch(
            index_x=0.5, index_y=0.5,
            thumb_x=0.5, thumb_y=0.54,  # dist 0.04 -> ratio 0.40
            wrist_x=0.5, wrist_y=0.7,
            middle_mcp_x=0.5, middle_mcp_y=0.6
        )
        self.assertFalse(pinching)

    def test_click_freeze_anchors_cursor_during_pinch(self):
        t = 1000.0
        # Normal open frame
        sx1, sy1, click1 = self.processor.process_frame(0.5, 0.5, False, timestamp=t)
        self.assertFalse(click1)

        # Pinch triggers click
        t += 0.03
        sx2, sy2, click2 = self.processor.process_frame(0.5, 0.5, True, timestamp=t)
        self.assertTrue(click2)
        frozen_anchor_x = sx2
        frozen_anchor_y = sy2

        # In next 50ms (within freeze_duration 0.12s), user's fingers shift slightly to 0.52, 0.52
        t += 0.05
        sx3, sy3, click3 = self.processor.process_frame(0.52, 0.52, True, timestamp=t)
        self.assertFalse(click3)
        # Position MUST remain anchored to prevent slipping off the button!
        self.assertEqual(sx3, frozen_anchor_x)
        self.assertEqual(sy3, frozen_anchor_y)

    def test_missing_landmark_grace_hold(self):
        t = 1000.0
        sx, sy, _ = self.processor.process_frame(0.5, 0.5, False, timestamp=t)

        # Drop landmark for 2 frames
        t += 0.033
        hold_x1, hold_y1, _ = self.processor.process_frame(None, None, False, timestamp=t)
        self.assertEqual(hold_x1, sx)
        self.assertEqual(hold_y1, sy)

        t += 0.033
        hold_x2, hold_y2, _ = self.processor.process_frame(None, None, False, timestamp=t)
        self.assertEqual(hold_x2, sx)

        # Long drop beyond grace period (more than 4 frames)
        for _ in range(5):
            t += 0.033
            lost_x, lost_y, _ = self.processor.process_frame(None, None, False, timestamp=t)

        self.assertIsNone(lost_x)
        self.assertIsNone(lost_y)

    def test_dynamic_sensitivity_and_smoothing_update(self):
        self.processor.update_settings(sensitivity=2.0, min_cutoff=1.5, beta=0.03)
        self.assertEqual(self.processor.sensitivity, 2.0)
        self.assertEqual(self.processor.filter_x.min_cutoff, 1.5)
        self.assertEqual(self.processor.filter_x.beta, 0.03)


if __name__ == "__main__":
    unittest.main()
