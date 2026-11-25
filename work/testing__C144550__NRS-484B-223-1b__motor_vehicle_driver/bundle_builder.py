"""Materialize exact current-runtime CPU construction bundles."""

from __future__ import annotations

import json
from pathlib import Path

from native_construction import ASSIGNMENT, VARIANTS


HERE = Path(__file__).resolve().parent
FILES = ("runner.py", "native_session.py", "native_construction.py",
         "native_readbacks.py", "camera_capture.py", "media_encode.py",
         "finalize_lane_change.py", "lane_change_timing.py", "analysis.py")


def construct(variant: str, candidate: str = "primary") -> dict:
    if variant not in VARIANTS:
        raise ValueError("unknown controlled lane-change case")
    if candidate not in ("primary", "fallback1"):
        raise ValueError("unknown lane-change engineering candidate")
    case_id = ASSIGNMENT + "__" + variant
    config = json.loads((HERE / "config.json").read_text())
    config["selected_case_id"] = case_id
    description = {
        "channels": [
            {"name": "original_lane_and_pose", "unit": "metres and seconds",
             "method": "Native actor pose and signed offset from reviewed source-lane centerline",
             "reference_frame": "reviewed source lane and original world frame",
             "sampling_rate_hz": 20, "time_window": "all 900 original world ticks",
             "uncertainty": "physical lane geometry and transition require local review"},
            {"name": "native_signal_state", "unit": "boolean API state",
             "method": "Original actor.get_light_state each Native world tick",
             "reference_frame": "original world frame", "sampling_rate_hz": 20,
             "time_window": "all 900 original world ticks",
             "uncertainty": "API signal state alone does not decide appropriateness"},
            {"name": "independent_driver_input", "unit": "boolean observed event",
             "method": "Separate source-ID-bound driver-input readback, joined to Native frame/time",
             "reference_frame": "original world frame", "sampling_rate_hz": 20,
             "time_window": "all 900 original world ticks",
             "uncertainty": "observed event does not prove mental ascertainment or safety"},
            {"name": "target_lane_traffic", "unit": "metres and metres per second",
             "method": "Original target actor transform and velocity on each world tick",
             "reference_frame": "reviewed destination lane and original world frame",
             "sampling_rate_hz": 20, "time_window": "all 900 original world ticks",
             "uncertainty": "relative gap and actual safety require local physical review"},
            {"name": "four_camera_views", "unit": "original RGB pixels",
             "method": "Four sensor BGRA frames converted to retained PNG and lossless FFV1",
             "reference_frame": "same-frame Native sensor clock", "sampling_rate_hz": 20,
             "time_window": "all 900 original world ticks",
             "uncertainty": "actual visibility requires local pixel audit"}],
        "context_inputs": [{"name": "reviewed_marked_multilane_highway",
                            "unit": "SHA-bound original map packet",
                            "method": "reviewed source, lane marking and live OpenDRIVE hash match"}],
        "limitations": ["Original accepted traces/video and reviewed map are absent in worker export.",
                        "Driver-input event is not a legal ascertainment finding."]}
    config["recording_description"] = description
    files = [{"path": name, "content": (HERE / name).read_text()} for name in FILES]
    if candidate == "fallback1":
        # Change only the ego route follower. The target traffic, signal and
        # independent driver-input policies stay identical across comparisons.
        code = next(item for item in files if item["path"] == "native_construction.py")
        original = code["content"]
        original_steer = "steer = max(-0.65, min(0.65, 1.2 * error))"
        original_throttle = "throttle=0.0 if arrived else 0.3,"
        if original.count(original_steer) != 1 or original.count(original_throttle) != 1:
            raise ValueError("ego controller fallback patch no longer matches source")
        code["content"] = original.replace(original_steer,
            "steer = max(-0.65, min(0.65, 0.85 * error))").replace(
            original_throttle, "throttle=0.0 if arrived else 0.22,")
    files.append({"path": "config.json", "content": json.dumps(config, indent=2, sort_keys=True) + "\n"})
    files.append({"path": "tests/test_bundle_smoke.py", "content":
        "import unittest\nfrom runner import check\n\n"
        "class BundleSmoke(unittest.TestCase):\n"
        "    def test_exact_case_and_capture(self):\n"
        "        c = check()\n"
        "        self.assertEqual(c['rate_hz'] * c['duration_s'], 900)\n"
        f"        self.assertEqual(c['selected_case_id'], {case_id!r})\n"})
    return {
        "law_id": "NRS-484B-223-1b", "cell_id": "C144550",
        "actor": "motor_vehicle_driver", "case_id": case_id,
        "entrypoint": "runner.py", "files": files,
        "measurement_plan": {
            "signal_lead_distance": "Original planar pose path integral from sole-left API onset to first source-lane center displacement >0.05m; retains sampled event bracket",
            "driver_check": "Independent source-ID, original-frame/time driver-input event before departure; not proof of ascertainment",
            "target_lane_traffic": "Original target actor position and velocity per tick; not proof of safety"},
        "recording_description": description,
        "mechanisms": ["SHA-bound reviewed marked same-direction lanes and live OpenDRIVE match",
                       "Owned ego and target-lane actor route control",
                       "Independent signal API and driver-input readbacks",
                       "Four original 20 Hz RGB cameras and synchronized primary video"],
        "static_checks": ["Exact law/cell/actor/case", "Reviewed lane geometry before world mutation",
                          "Four original 900-frame camera and readback joins", "Owned restoration readback"],
        "termination_rules": ["900 original 20 Hz frames or fail closed on missing source/time",
                              "Actual physical completion and legal judgment remain local review"]}


def build():
    root = HERE / "cases"
    for variant in VARIANTS:
        target = root / variant / "construction.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(construct(variant), indent=2, sort_keys=True) + "\n")
        fallback = root / variant / "fallback1" / "construction.json"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        fallback.write_text(json.dumps(construct(variant, "fallback1"), indent=2,
            sort_keys=True) + "\n")
    (HERE / "construction.json").write_text(
        json.dumps(construct("both_observed"), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    build()
