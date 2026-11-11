"""Add three separate physical-risk alternatives to each exception case."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "execution-manifest.json"


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError("Expected exactly one variant knob: " + before)
    return text.replace(before, after)


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        if suffix not in ("ordinary_police_at500", "authorized_police_at500"):
            continue
        folder = HERE / "cases" / suffix
        primary = json.loads((folder / "construction.json").read_text())
        variants = [
            ("fallback1", "runner.py",
             "select_intersection_route(world.get_map(), target_gap_ft=500)",
             "select_intersection_route(world.get_map(), target_gap_ft=500, step_m=2.5)",
             "Native route sample step 5 m to 2.5 m",
             {"source": "Native waypoint route-selection diagnostic",
              "metric": "connected through-intersection route count",
              "failure_condition": "Primary 5 m sampling finds no connected route with the junction between actors"}),
            ("fallback2", "runner.py",
             "control_step(ego, apparatus, target_gap_ft=500,\n                         steer=",
             "control_step(ego, apparatus, target_gap_ft=500,\n                         gain=0.12, speed_gain=0.22, steer=",
             "following gap and speed feedback gains 0.18/0.30 to 0.12/0.22",
             {"source": "original participant footprint and state streams",
              "metric": "active-frame gap oscillation around commanded 500 ft",
              "failure_condition": "Primary gain produces sustained gap oscillation outside a predeclared engineering attainment band"}),
            ("fallback3", "fire_camera_capture.py",
             '"approach": ((1.2, 0.0, 2.0), (0.0, 0.0, 0.0), (1280, 720), 90)',
             '"approach": ((1.8, 0.0, 2.3), (0.0, 0.0, 0.0), (1280, 720), 90)',
             "approach camera mount 1.2 m forward/2.0 m high to 1.8 m forward/2.3 m high",
             {"source": "decoded original approach and overview RGB streams",
              "metric": "required participant body pixels in original frames",
              "failure_condition": "Primary approach view omits a required participant body in any original frame"}),
        ]
        entry["candidates"] = []
        for label, filename, before, after, knob, trigger in variants:
            data = deepcopy(primary)
            data["candidate_id"] = label
            file = next(row for row in data["files"] if row["path"] == filename)
            file["content"] = once(file["content"], before, after)
            path = folder / (label + "-construction.json")
            save(path, data)
            entry["candidates"].append({
                "id": label, "construction": path.relative_to(HERE).as_posix(),
                "construction_sha256": sha256(path.read_bytes()).hexdigest(),
                "trigger": trigger, "changed_knobs": [knob]})
    save(MANIFEST, manifest)


if __name__ == "__main__":
    main()
