"""Independent original-source comparison of the three passing-distance cases."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DISTANCES = (70, 120, 170)
FIXED_REQUEST_KEYS = ("ego_blueprint_request", "ego_center_xy_m", "ego_speed_mps",
                      "overtaken_center_xy_m", "overtaken_speed_mps",
                      "oncoming_speed_mps", "sightline_assumed_visible", "source_kind")
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    path = Path(path)
    require(path.is_file(), "Missing comparison source: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def compare_requested(paths):
    originals = {distance: rows(paths[distance]) for distance in DISTANCES}
    reference = originals[70]
    require(all(len(originals[d]) == 600 for d in DISTANCES), "Comparison lacks full 600-frame requests")
    for distance in DISTANCES:
        for i, (baseline, item) in enumerate(zip(reference, originals[distance])):
            require(item["frame"] == baseline["frame"] == i and
                    abs(item["time_s"] - baseline["time_s"]) < 1e-6,
                    "Requested frame clock differs")
            require(all(item.get(key) == baseline.get(key) for key in FIXED_REQUEST_KEYS),
                    "Undeclared fixed requested condition changed")
            require(item["requested_driver_eye_clear_m"] == distance and
                    item["requested_entry_oncoming_body_gap_m"] == distance,
                    "Selected request differs from comparison distance")
            require(abs(item["oncoming_center_xy_m"][0] - baseline["oncoming_center_xy_m"][0] - (distance - 70)) < 1e-6 and
                    item["oncoming_center_xy_m"][1] == baseline["oncoming_center_xy_m"][1],
                    "Oncoming requested trajectory changed beyond distance axis")
    return {str(d): sha(paths[d]) for d in DISTANCES}


def audit(attempts, output):
    requests = {distance: attempts[distance] / "requested-tracks.jsonl" for distance in DISTANCES}
    request_hashes = compare_requested(requests)
    roads = {sha(attempts[d] / "road.xodr") for d in DISTANCES}
    require(len(roads) == 1, "Fixed road geometry changed")
    measurements = {}
    for distance in DISTANCES:
        root = attempts[distance]
        provenance = json.loads((root / "acquisition-provenance.json").read_text())
        require(provenance.get("provenance_kind") == "original_native" and
                provenance.get("diagnostic_fixture") is False,
                "Synthetic fixture cannot establish original comparison")
        config = json.loads((root / "config.json").read_text())
        require(config.get("selected_case_id") == HERE.name + "__" + str(distance) and
                config.get("candidate_id") == "primary" and
                config.get("duration_s") == 30 and config.get("rate_hz") == 20 and
                [camera.get("name") for camera in config.get("cameras", [])] == list(CAMERAS),
                "Fixed selected case or capture profile changed")
        native = rows(root / "native-observed.jsonl")
        trace = rows(root / "trace.jsonl")
        mapping = rows(root / "video_frames.jsonl")
        require(len(native) == len(trace) == len(mapping) == 600,
                "Original comparison lacks full 600-frame join")
        for n, t, m in zip(native, trace, mapping):
            require(n.get("native_frame") == t.get("frame") == m.get("carla_frame") and
                    abs(n["time_s"] - t["time_s"]) < 1e-4 and
                    abs(n["time_s"] - m["time_s"]) < 1e-4,
                    "Original comparison frame/time join changed")
            require(all(isinstance(n.get(role), dict) for role in ("ego", "overtaken", "oncoming")),
                    "Original comparison participant missing")
        measurements[str(distance)] = {
            "native_source_sha256": sha(root / "native-observed.jsonl"),
            "trace_sha256": sha(root / "trace.jsonl"),
            "frame_map_sha256": sha(root / "video_frames.jsonl"),
            "requested_distance_m": distance,
            "first_sample_oncoming_center_gap_m": native[0]["oncoming"]["center_native_xyz_m"][0] - native[0]["ego"]["center_native_xyz_m"][0],
            "legal_sufficiency_judgment": None,
        }
    receipt = {"format": "c102951-original-comparison-audit-v1", "passed": True,
               "cases": [HERE.name + "__" + str(d) for d in DISTANCES],
               "request_hashes": request_hashes, "road_sha256": next(iter(roads)),
               "source_measurements": measurements,
               "comparison_axis": "requested_oncoming_distance_m",
               "fixed_conditions_checked": list(FIXED_REQUEST_KEYS) + ["road.xodr", "camera profile", "30 s / 20 Hz frame join"],
               "statutory_sufficiency_or_interference_claimed": False}
    Path(output).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for distance in DISTANCES:
        parser.add_argument(f"--attempt-{distance}", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    audit({d: Path(getattr(args, f"attempt_{d}")).resolve() for d in DISTANCES}, args.output)
