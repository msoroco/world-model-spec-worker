"""Exact signal package identity, camera profile and required channels."""

AID = "testing__C158196__NRS-484B-307-6a__motor_vehicle_driver"
LAW = "NRS-484B-307-6a"
CELL = "C158196"
ACTOR = "motor_vehicle_driver"
CAMERA_NAMES = ("overview", "approach", "reference_corner", "driver_reference")
CAMERAS = [{"name": name, "width": 1920 if index == 0 else 1280,
            "height": 1080 if index == 0 else 720, "fov_deg": 75,
            "pose_strategy": "surveyed entry polygon and official route-facing head"}
           for index, name in enumerate(CAMERA_NAMES)]
CHANNELS = (
    ("selected_facing_signal_sequence", "original state/frame", "official bound vehicular signal readback at 20 Hz"),
    ("intersection_entry_bracket", "world meters/frame", "ego front body versus surveyed entry polygon"),
    ("signal_vs_entry", "original frame bracket", "green/yellow/red transitions relative to body entry"),
    ("comparison_isolation", "source record", "fixed Native route and realized changed indication or entry"),
    ("camera_frame_identity", "original frame", "four synchronized Native RGB cameras"),
)
RECORDING = {
    "channels": [{"name": name, "unit": unit, "method": method,
                  "sampling_rate_hz": 20, "time_window": "45-second signal interval",
                  "reference_frame": "surveyed Native map and original world snapshot",
                  "uncertainty": "20 Hz phase/entry bracket and legal reading require review"}
                 for name, unit, method in CHANNELS],
    "context_inputs": [{"name": "reviewed_native_signal_scene", "unit": "source record",
                        "method": "hash-sealed map, polygon, route and official devices"}],
    "limitations": ["Synthetic fixtures establish software compatibility only.",
                    "The meaning of immediately thereafter and intersection entry remains for legal review."]}
