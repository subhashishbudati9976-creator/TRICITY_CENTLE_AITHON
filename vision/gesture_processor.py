"""
AirControl — Precision Gesture & Cursor Processing Engine
Implements adaptive One Euro filtering, coordinate mapping with active interaction box,
pinch hysteresis, click-freeze anchoring, and tracking loss grace hold.
"""

import math
import time
from typing import Optional, Tuple


class LowPassFilter:
    """First-order low-pass filter with exponential smoothing."""

    def __init__(self, alpha: float = 0.5):
        self.alpha = alpha
        self.y = None
        self.s = None

    def filter(self, value: float, alpha: Optional[float] = None) -> float:
        if alpha is not None:
            self.alpha = alpha
        if self.s is None:
            self.s = value
        else:
            self.s = self.alpha * value + (1.0 - self.alpha) * self.s
        self.y = value
        return self.s

    def reset(self):
        self.y = None
        self.s = None


class OneEuroFilter:
    """
    1€ Filter (Casiez, Roussel, Vogel - CHI 2012)
    Provides zero-jitter precision at low velocities and near-zero lag at high velocities.
    """

    def __init__(
        self,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
    ):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self.x_filt = LowPassFilter()
        self.dx_filt = LowPassFilter()
        self.last_time: Optional[float] = None

    def _alpha(self, rate: float, cutoff: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        te = 1.0 / rate if rate > 0 else 0.016
        return 1.0 / (1.0 + tau / te)

    def filter(self, x: float, timestamp: Optional[float] = None) -> float:
        if timestamp is None:
            timestamp = time.monotonic()

        if self.last_time is None or self.x_filt.s is None:
            self.last_time = timestamp
            self.dx_filt.filter(0.0)
            return self.x_filt.filter(x)

        dt = timestamp - self.last_time
        # Prevent division by zero or extreme delta jumps
        if dt <= 1e-4:
            return self.x_filt.s if self.x_filt.s is not None else x

        self.last_time = timestamp
        rate = 1.0 / dt

        # Estimate derivative of the signal
        prev_s = self.x_filt.s if self.x_filt.s is not None else x
        dx = (x - prev_s) * rate
        edx = self.dx_filt.filter(dx, self._alpha(rate, self.d_cutoff))

        # Dynamic cutoff frequency based on velocity magnitude
        cutoff = self.min_cutoff + self.beta * abs(edx)
        return self.x_filt.filter(x, self._alpha(rate, cutoff))

    def reset(self):
        self.x_filt.reset()
        self.dx_filt.reset()
        self.last_time = None


class GestureProcessor:
    """
    Translates raw normalized hand landmarks into stable, jitter-free desktop coordinates
    with pinch hysteresis, click-freeze anchoring, and drop-frame resilience.
    """

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        sensitivity: float = 1.0,
        min_cutoff: float = 0.8,
        beta: float = 0.015,
        pinch_down_threshold: float = 0.28,
        pinch_up_threshold: float = 0.35,
        click_cooldown: float = 0.40,
        freeze_duration: float = 0.12,
        box_margin_x: float = 0.12,
        box_margin_y: float = 0.12,
    ):
        self.screen_w = max(100, screen_w)
        self.screen_h = max(100, screen_h)
        self.sensitivity = max(0.2, min(3.0, sensitivity))

        # Interaction active region in normalized camera space [0..1]
        self.box_margin_x = box_margin_x
        self.box_margin_y = box_margin_y

        # One Euro filters for screen coordinates
        self.filter_x = OneEuroFilter(min_cutoff=min_cutoff, beta=beta)
        self.filter_y = OneEuroFilter(min_cutoff=min_cutoff, beta=beta)

        # Hysteresis thresholds for pinch
        self.pinch_down_threshold = pinch_down_threshold
        self.pinch_up_threshold = pinch_up_threshold
        self.click_cooldown = click_cooldown
        self.freeze_duration = freeze_duration

        # State tracking
        self.is_pinching = False
        self.last_click_time = 0.0
        self.last_pinch_start = 0.0
        self.frozen_x: Optional[float] = None
        self.frozen_y: Optional[float] = None

        # Tracking drop resilience (hold position briefly during occlusions)
        self.consecutive_missing = 0
        self.max_missing_grace = 4  # hold for ~4 frames (~100-130ms at 30fps)
        self.last_valid_screen_x: Optional[float] = None
        self.last_valid_screen_y: Optional[float] = None

    def update_settings(
        self,
        sensitivity: Optional[float] = None,
        min_cutoff: Optional[float] = None,
        beta: Optional[float] = None,
        click_cooldown: Optional[float] = None,
    ):
        """Allows dynamic live tuning of sensitivity and smoothing parameters."""
        if sensitivity is not None:
            self.sensitivity = max(0.2, min(3.0, sensitivity))
        if min_cutoff is not None:
            self.filter_x.min_cutoff = float(min_cutoff)
            self.filter_y.min_cutoff = float(min_cutoff)
        if beta is not None:
            self.filter_x.beta = float(beta)
            self.filter_y.beta = float(beta)
        if click_cooldown is not None:
            self.click_cooldown = max(0.1, float(click_cooldown))

    def map_coordinates(self, norm_x: float, norm_y: float) -> Tuple[float, float]:
        """
        Maps normalized camera coordinates [0..1] into screen pixels [0..SCREEN_DIM],
        accounting for active interaction margin and sensitivity scaling.
        """
        # Active region normalized bounds
        min_x = self.box_margin_x
        max_x = 1.0 - self.box_margin_x
        min_y = self.box_margin_y
        max_y = 1.0 - self.box_margin_y

        # Clamp into active box
        clamped_x = max(min_x, min(max_x, norm_x))
        clamped_y = max(min_y, min(max_y, norm_y))

        # Normalized to [0..1] within active bounding box
        span_x = max(0.01, max_x - min_x)
        span_y = max(0.01, max_y - min_y)
        box_x = (clamped_x - min_x) / span_x
        box_y = (clamped_y - min_y) / span_y

        # Apply sensitivity centered at 0.5
        adj_x = 0.5 + (box_x - 0.5) * self.sensitivity
        adj_y = 0.5 + (box_y - 0.5) * self.sensitivity
        adj_x = max(0.0, min(1.0, adj_x))
        adj_y = max(0.0, min(1.0, adj_y))

        # Screen boundary padding so cursor can comfortably touch edges without hitting corners
        padding = 15
        target_x = padding + adj_x * (self.screen_w - 2 * padding)
        target_y = padding + adj_y * (self.screen_h - 2 * padding)
        return target_x, target_y

    def calculate_pinch(
        self,
        index_x: float,
        index_y: float,
        thumb_x: float,
        thumb_y: float,
        wrist_x: float,
        wrist_y: float,
        middle_mcp_x: float,
        middle_mcp_y: float,
    ) -> Tuple[bool, float]:
        """
        Evaluates pinch gesture state using Schmitt trigger (hysteresis).
        Returns (is_pinching, pinch_ratio).
        """
        pinch_dist = math.hypot(index_x - thumb_x, index_y - thumb_y)
        palm_size = math.hypot(middle_mcp_x - wrist_x, middle_mcp_y - wrist_y)
        pinch_ratio = pinch_dist / palm_size if palm_size > 0.001 else 1.0

        if not self.is_pinching:
            # Entering pinch requires reaching the tighter threshold
            if pinch_ratio < self.pinch_down_threshold:
                self.is_pinching = True
        else:
            # Exiting pinch requires relaxing beyond the upper threshold
            if pinch_ratio > self.pinch_up_threshold:
                self.is_pinching = False

        return self.is_pinching, pinch_ratio

    def process_frame(
        self,
        norm_x: Optional[float],
        norm_y: Optional[float],
        raw_pinching: bool,
        timestamp: Optional[float] = None,
    ) -> Tuple[Optional[int], Optional[int], bool]:
        """
        Processes a single input sample.
        Returns:
            (cursor_screen_x, cursor_screen_y, trigger_click_event)
        """
        if timestamp is None:
            timestamp = time.monotonic()

        # Handle missing hand detection
        if norm_x is None or norm_y is None:
            self.consecutive_missing += 1
            if self.consecutive_missing <= self.max_missing_grace and self.last_valid_screen_x is not None:
                # Hold previous filtered position during brief dropouts
                return int(self.last_valid_screen_x), int(self.last_valid_screen_y), False
            # Beyond grace period, reset filter states to prevent teleporting
            self.reset()
            return None, None, False

        self.consecutive_missing = 0

        # Map to screen coordinates
        target_x, target_y = self.map_coordinates(norm_x, norm_y)

        # Smooth using One Euro Filter
        filtered_x = self.filter_x.filter(target_x, timestamp=timestamp)
        filtered_y = self.filter_y.filter(target_y, timestamp=timestamp)

        # Check click triggering with freeze anchor
        trigger_click = False
        now = timestamp

        # Determine transition
        was_pinching = self.is_pinching
        self.is_pinching = raw_pinching

        if self.is_pinching and not was_pinching:
            # Just entered pinch
            if now - self.last_click_time >= self.click_cooldown:
                trigger_click = True
                self.last_click_time = now
                self.last_pinch_start = now
                # Anchor cursor position so the click doesn't move off target
                self.frozen_x = filtered_x
                self.frozen_y = filtered_y

        # If currently in a click freeze window, hold anchored coordinates
        if self.is_pinching and self.frozen_x is not None and (now - self.last_pinch_start < self.freeze_duration):
            out_x = self.frozen_x
            out_y = self.frozen_y
        else:
            if not self.is_pinching:
                self.frozen_x = None
                self.frozen_y = None
            out_x = filtered_x
            out_y = filtered_y

        self.last_valid_screen_x = out_x
        self.last_valid_screen_y = out_y

        return int(round(out_x)), int(round(out_y)), trigger_click

    def reset(self):
        """Reset internal filter states when tracking is lost or paused."""
        self.filter_x.reset()
        self.filter_y.reset()
        self.is_pinching = False
        self.frozen_x = None
        self.frozen_y = None
        self.last_valid_screen_x = None
        self.last_valid_screen_y = None
        self.consecutive_missing = 0
