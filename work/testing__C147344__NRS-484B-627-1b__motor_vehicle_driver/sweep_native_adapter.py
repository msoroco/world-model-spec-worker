"""Native capture extension for source-gated sweep speed readback."""
from __future__ import annotations

import math

from native_adapter import NativeAdapter


class SweepNativeAdapter(NativeAdapter):
    def tick_and_capture(self, frame: int, hz: int, actors: dict, cameras: dict):
        super().tick_and_capture(frame, hz, actors, cameras)
        if "slower_vehicle" in actors:
            velocity = actors["slower_vehicle"].get_velocity()
            self.motion_rows[-1]["slower_vehicle_speed_mps"] = math.sqrt(
                velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
