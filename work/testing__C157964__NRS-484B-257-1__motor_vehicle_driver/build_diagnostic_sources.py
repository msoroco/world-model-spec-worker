"""Build text-only, synthetic source recipes for saved officer software checks."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
TEMPLATE = REPO / "work/testing__C158196__NRS-484B-257-1__motor_vehicle_driver/officer-controlled-diagnostic-sources.json"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def body(x, y=0):
    return [[x + dx, y + dy] for dx, dy in ((-1, -1), (-1, 1), (1, 1), (1, -1))]


def through_body():
    return [[x, y] for x, y in ((-1, -1), (-1, 1), (1, 1), (1, -1)) for _ in (0, 1)]


def build(case_id, template):
    suffix = case_id.rsplit("__", 1)[-1]
    absent = suffix == "no_officer_yield_nearest_view"
    inactive = suffix == "officer_present_inactive"
    hold = suffix == "officer_active_hold"
    directions = ["none"] * 3 if absent or inactive else ["stop", "stop", "stop" if hold else "go"]
    times = tuple(json.loads(line)["time_s"] for line in
                  template["files"]["trace.jsonl"].splitlines())
    frames = (100, 101, 102)
    ctx = json.loads((ROOT / "config.json").read_text())["officer_context"]
    ctx = dict(ctx, case_id=case_id, officer_actor_id=None if absent else 303, through_actor_id=102)
    if absent:
        for key in ("authority_source", "uniform_video_source"):
            ctx[key] = None
    rows = []
    for index, frame in enumerate(frames):
        rows.append({"frame": frame, "time_s": times[index],
                     "officer_actor_id": ctx["officer_actor_id"],
                     "programmed_direction": directions[index],
                     "pose_applied": not (absent or inactive),
                     "realized_bones": ({"arm_right": {"pitch": 90 if directions[index] == "stop" else 0}}
                                        if not (absent or inactive) else {}),
                     "ego": {"speed_mps": 0 if index < 2 else 2,
                             "body_vertices_xy_m": body((-15, -15, -3)[index])},
                     "through": {"actor_id": 102, "speed_mps": 3,
                                 "body_vertices_xy_m": through_body()}})
    mapping = [{"video_frame": i, "carla_frame": frame, "native_frame": frame,
                "time_s": times[i], "camera_frames": {name: frame for name in CAMERAS}}
               for i, frame in enumerate(frames)]
    history = "".join(encoded(row) for row in rows)
    frame_text = "".join(encoded(row) for row in mapping)
    original_review = json.loads(template["files"]["officer_review.json"])
    review = {"provenance_kind": "synthetic_fixture",
              "officer_history_sha256": digest(history), "video_frames_sha256": digest(frame_text),
              "camera_sha256": original_review["camera_sha256"],
              "frames": [{"frame": frame, "video_frame": i,
                          "observed_direction": directions[i],
                          "traffic_control_observed": not (absent or inactive),
                          "direction_frame_source": "approach.mkv" if not absent else "four-original-camera-absence-review",
                          "officer_visible": not absent} for i, frame in enumerate(frames)]}
    files = {key: value for key, value in template["files"].items()
             if key in ("trace.jsonl", "capture/evidence.jsonl", "capture/native/frames.jsonl",
                        "capture/recorder_info.txt")}
    files.update({"officer_context.json": encoded(ctx), "officer_history.jsonl": history,
                  "video_frames.jsonl": frame_text, "officer_review.json": encoded(review)})
    manifest = json.loads(template["files"]["capture/manifest.json"])
    manifest.update(case_id=case_id, sources={"road.xodr": digest((ROOT / "officer-site.xodr").read_text()),
                                               "trace.jsonl": digest(files["trace.jsonl"])})
    files["capture/manifest.json"] = encoded(manifest)
    return {"files": files, "graphs": template["graphs"], "videos": template["videos"]}


def main():
    template = json.loads(TEMPLATE.read_text())
    for case in json.loads((ROOT / "case-plan.json").read_text())["cases"]:
        case_id = case["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        spec_path = ROOT / (suffix + "-diagnostic-sources.json")
        spec_path.write_text(json.dumps(build(case_id, template), indent=2, allow_nan=False) + "\n")
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "road.xodr",
                               "source": str((ROOT / "officer-site.xodr").relative_to(REPO)),
                               "sha256": digest((ROOT / "officer-site.xodr").read_text())}],
                  "generator": {"source": str(spec_path.relative_to(REPO)),
                                "sha256": digest(spec_path.read_text())}}
        (ROOT / (suffix + "-fixture-recipe.json")).write_text(json.dumps(recipe, indent=2) + "\n")
        print(suffix)


if __name__ == "__main__":
    main()
