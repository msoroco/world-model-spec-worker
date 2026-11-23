"""Canonical raw recording description shared by the three C150530 attempts."""
from __future__ import annotations


def build() -> dict:
    channel_names = (
        ("original_motion", "Original 20 Hz cab pose, heading, speed, road and lane identity."),
        ("controller_history", "Original 20 Hz throttle, brake, steer and target waypoint."),
        ("camera_frame_map", "Original 20 Hz Native frame/time to all camera frames."),
        ("overview_rgb", "Original 20 Hz stand-to-junction overhead RGB frames."),
        ("approach_rgb", "Original 20 Hz stand and posted-notice RGB frames."),
        ("reference_corner_rgb", "Original 20 Hz junction and receiving-road RGB frames."),
        ("driver_reference_rgb", "Original 20 Hz cab-forward RGB frames."),
    )
    return {
        "channels": [{"name": name, "unit": "structured record" if not name.endswith("_rgb") else "RGB frame",
                      "sampling_rate_hz": 20, "method": method,
                      "time_window": "full original stand departure through first-junction attempt",
                      "reference_frame": "original CARLA world frame and synchronized 20 Hz time",
                      "uncertainty": "20 Hz sample spacing; geometry and pixel visibility require physical review"}
                     for name, method in channel_names],
        "context_inputs": [
            {"name": name, "unit": "source-hashed record", "method": method}
            for name, method in (
                ("cab_license", "Retained original cab licensing source and review."),
                ("stand_designation", "Retained original stand designation source and review."),
                ("stand_marking", "Retained original stand marking source and review."),
                ("posted_notice", "Retained original posted right-turn notice source and review."),
                ("jurisdiction", "Retained original jurisdiction source and review."),
                ("designation_provisions", "Retained original referenced designation provisions and applicability review."),
            )],
        "limitations": ["Original documentary context and Native camera pixels remain unverified.",
                        "Measured turn geometry is an engineering observation, not a legal verdict."],
    }
