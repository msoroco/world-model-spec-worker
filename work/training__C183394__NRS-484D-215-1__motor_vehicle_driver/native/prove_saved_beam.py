"""Source-bound recorded-only measurement positive and negative diagnostics."""
import json
import os
from pathlib import Path
import shutil

from beam_scene import beam_request
from saved_beam import CAMERAS, SOURCES, measure_saved, sha


def reject(action, phrase):
    try:
        action()
    except ValueError as error:
        assert phrase in str(error), str(error)
    else:
        raise AssertionError("expected rejection: " + phrase)


root = Path(os.environ["TMPDIR"]).resolve() / "saved-beam-proof"
assert ".runtime-work" in root.parts
if root.exists():
    shutil.rmtree(root)
root.mkdir(parents=True)


def put(name, data):
    (root / name).write_text(data if isinstance(data, str) else json.dumps(data) + "\n")


put("road.xodr", "<OpenDRIVE><road id=\"183394\"/></OpenDRIVE>\n")
put("road-position-source.json", {"road_position": "adjacent_shoulder",
                                  "map_and_adjacency_source": "synthetic diagnostic road"})
put("lighting-trigger-source.json", {"lighting_trigger": "night_interval",
    "original_trigger_source": "synthetic clock", "NRS_484D_100_review_required": True})
put("oncoming-driver-source.json", {"oncoming_actor_source": "synthetic opposed actor"})
put("eye-region-source.json", {"driver_reference_camera": "driver_reference",
                                    "pixel_review_required": True})
rows, frames = [], []
for i in range(600):
    t = i / 20
    distance = 300 - 10*t
    rows.append({"frame": i, "native_frame": 1000 + i, "time_s": t,
        "ego_x_m": 5*t, "ego_y_m": -5.0, "ego_heading_x": 1, "ego_heading_y": 0,
        "oncoming_x_m": 300 - 5*t, "oncoming_y_m": 1.75,
        "oncoming_heading_x": -1, "oncoming_heading_y": 0,
        "requested_beam_state": beam_request("dim_within_500", distance),
        "observed_light_state_bits": 3 if beam_request("dim_within_500", distance) == "low_beam" else 5,
        "lamp_state_source": "synthetic readback",
        "eye_region_pixels_retained": True})
    frames.append({"video_frame": i, "native_frame": 1000 + i, "time_s": t})
put("beam-rows.jsonl", "".join(json.dumps(row) + "\n" for row in rows))
put("video_frames.jsonl", "".join(json.dumps(row) + "\n" for row in frames))
for camera in CAMERAS:
    put(camera + ".mkv", "diagnostic placeholder; no video decode claimed\n")
context = {"case_id": "training__C183394__NRS-484D-215-1__motor_vehicle_driver__selected_6fb122bc__condition_a",
           "deeming_invoked": False, "legal_verdict_claimed": False,
           "source_sha256": {name: sha(root / name) for name in SOURCES}}
put("config.json", {"selected_case_id": context["case_id"]})
put("beam-context.json", context)
result = measure_saved(root)
assert result["measurement"]["within_500_feet_frames"] > 0
assert result["original_pixels_reviewed"] is False
eye = root / "eye-region-source.json"
eye.write_text(json.dumps({"driver_reference_camera": "driver_reference", "pixel_review_required": False}) + "\n")
reject(lambda: measure_saved(root), "source hash differs")
put("beam-context.json", dict(context, source_sha256={
    **context["source_sha256"], "eye-region-source.json": sha(eye)}))
reject(lambda: measure_saved(root), "eye-region source required")
put("eye-region-source.json", {"driver_reference_camera": "driver_reference", "pixel_review_required": True})
frames[10]["native_frame"] = 9999
put("video_frames.jsonl", "".join(json.dumps(row) + "\n" for row in frames))
put("beam-context.json", dict(context, source_sha256={
    **context["source_sha256"], "video_frames.jsonl": sha(root / "video_frames.jsonl")}))
reject(lambda: measure_saved(root), "600-frame join")
print("PASS: 600-frame saved beam source join and stale/eye/missing-frame negatives")
