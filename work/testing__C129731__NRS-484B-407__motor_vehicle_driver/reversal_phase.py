"""Observed-heading phase marker for a source-gated Native reversal attempt.

This marks the physical heading-change interval for capture. A legal U-turn or
driver visibility determination requires separate original-source review.
"""
from __future__ import annotations

import math


def _delta_degrees(start: float, current: float) -> float:
    return abs((current - start + 180.0) % 360.0 - 180.0)


class HeadingReversalPhase:
    def __init__(self, start_threshold_deg: float = 2.0,
                 finish_threshold_deg: float = 165.0):
        if not 0 < start_threshold_deg < finish_threshold_deg < 180:
            raise ValueError("invalid observed heading thresholds")
        self.start_threshold_deg = start_threshold_deg
        self.finish_threshold_deg = finish_threshold_deg
        self.initial_yaw = None
        self.previous_frame = None
        self.started = False
        self.finished = False

    def __call__(self, frame: int, actor) -> bool:
        if type(frame) is not int or (self.previous_frame is not None and
                                      frame != self.previous_frame + 1):
            raise ValueError("observed turn phase needs consecutive Native frames")
        yaw = float(actor.get_transform().rotation.yaw)
        if not math.isfinite(yaw):
            raise ValueError("observed turn heading must be finite")
        self.previous_frame = frame
        if self.initial_yaw is None:
            self.initial_yaw = yaw
        if self.finished:
            return False
        delta = _delta_degrees(self.initial_yaw, yaw)
        if not self.started and delta >= self.start_threshold_deg:
            self.started = True
        if self.started and delta >= self.finish_threshold_deg:
            self.finished = True
        return self.started
