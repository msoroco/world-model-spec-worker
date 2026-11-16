"""Independent CPU audit of the three source-joined button placement members."""

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
POINTS = {"0000": 0.0, "0001": 1.0, "0002": 0.5}
FIXED_FILES = (
    "authority_source_original.json", "turn_originals.jsonl", "turn_body.jsonl",
    "body_history.jsonl", "video_frames.jsonl", "trace.jsonl",
    "overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def check(negative=False):
    manifest = json.loads((PACKAGE / "indication-provisional-manifest.json").read_text())
    entries = {case["case_id"][-4:]: case for case in manifest["cases"]}
    require(set(entries) == set(POINTS), "Numeric placement member set changed")
    source_digest = None
    fixed_digests = None
    proof = []
    for point, expected in POINTS.items():
        case = entries[point]
        attempt = ROOT / ".runtime-work" / f"c126064-indication-offset-{point}-saved-attempt"
        analysis = ROOT / ".runtime-work" / f"c126064-indication-offset-{point}-saved" / "v0001" / "analysis"
        require(attempt.is_dir() and analysis.is_dir(), "Missing original saved attempt or processing")
        source = json.loads((attempt / "authority_source_original.json").read_text())
        scene = json.loads((attempt / "marked_intersection.json").read_text())
        if negative and point == "0001":
            source["indications"][0]["x"] = 0.25
        require(source["indication_form"] == "button", "Original indication form changed")
        require(source["placement_axis_xy"] == [1.0, 0.0], "Original placement axis changed")
        require(source["indications"] == [{"form": "button", "x": 0.0, "y": 0.0}], "Original source button changed")
        require(scene["case_id"] == case["case_id"], "Scene case mismatch")
        require(scene["authority_source_sha256"] == digest(attempt / "authority_source_original.json"), "Source hash join failed")
        require(scene["indication_form"] == "button", "Scene form changed")
        require(scene["indicated_course_xy_m"] == source["indicated_course_xy_m"], "Indicated route changed")
        require(scene["intersection_polygon_xy_m"] == source["intersection_polygon_xy_m"], "Intersection changed")
        require(scene.get("source_indications_xy_m", [[0.0, 0.0]]) == [[0.0, 0.0]], "Source pose changed")
        require(scene["physical_indications_xy_m"] == [[expected, 0.0]], "Native physical readback changed")
        require(abs(float(scene.get("placement_offset_m", 0.0)) - expected) < 1e-9, "Placement setpoint changed")
        if point != "0000":
            require(scene["realized_placement_offset_m"] == [expected], "Native realized offset changed")
        values = rows(analysis / "realized_indication_placement_offset_m.jsonl")
        frames = rows(attempt / "video_frames.jsonl")
        require(len(values) == len(frames) == 9, "Measurement frame coverage changed")
        require(all(abs(float(v["value"]) - expected) < 1e-9 and v["frame"] == f["native_frame"] for v, f in zip(values, frames)), "Measured offset or frame join changed")
        current = {name: digest(attempt / name) for name in FIXED_FILES}
        require(source_digest is None or current["authority_source_original.json"] == source_digest, "Source hash changed across members")
        require(fixed_digests is None or current == fixed_digests, "Actor, body, frame, or camera original changed")
        source_digest = current["authority_source_original.json"]
        fixed_digests = current
        proof.append({"case_id": case["case_id"], "source_sha256": source_digest, "setpoint_m": expected, "measured_frames": len(values)})
    return {"passed": True, "scope": "CPU diagnostic original attempts; no municipal authority or physical pixel acceptance", "members": proof}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(args.negative), sort_keys=True))
