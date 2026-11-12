"""Independent original-source audit of the baseline right/left body contrast."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from right_half_measurement import measure


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def audit(right_root, left_root):
    right_root, left_root = Path(right_root), Path(left_root)
    if right_root.resolve() == left_root.resolve():
        raise ValueError("Baseline comparison repeats one source")
    files = ("ego_road_frames.jsonl", "road_exception_context.json")
    for root in (right_root, left_root):
        if any(not (root / name).is_file() for name in files):
            raise ValueError("Missing original baseline comparison source")
    if (right_root / files[1]).read_bytes() != (left_root / files[1]).read_bytes():
        raise ValueError("Baseline exception context changed")
    right = measure(*(right_root / name for name in files))
    left = measure(*(left_root / name for name in files))
    right_rows, left_rows = (_rows(root / files[0]) for root in (right_root, left_root))
    if len(right_rows) != len(left_rows):
        raise ValueError("Baseline original frame count changed")
    fixed = ("frame", "time_s", "road_id", "lane_id", "road_center_xy",
             "road_travel_tangent_xy", "road_width_m")
    for first, second in zip(right_rows, left_rows):
        if any(first.get(key) != second.get(key) for key in fixed):
            raise ValueError("Baseline road or original frame conditions changed")
    right_obs, left_obs = right["observations"], left["observations"]
    if not all(row["whole_body_right_half"] for row in right_obs):
        raise ValueError("Right baseline body is not wholly on right half")
    if not all(row["whole_body_left_half"] for row in left_obs):
        raise ValueError("Left baseline body is not wholly on left half")
    return {"format": "worker-right-half-baseline-comparison",
            "frames": len(right_rows),
            "fixed_original_keys": list(fixed) + [files[1]],
            "right_source_sha256": _digest(right_root / files[0]),
            "left_source_sha256": _digest(left_root / files[0]),
            "exception_context_sha256": _digest(right_root / files[1]),
            "right_maximum_lateral_m": max(row["maximum_signed_lateral_m"]
                                           for row in right_obs),
            "left_minimum_lateral_m": min(row["minimum_signed_lateral_m"]
                                          for row in left_obs),
            "legal_exception_or_compliance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--right", required=True)
    parser.add_argument("--left", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = audit(args.right, args.left)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"frames": result["frames"],
                      "right_source_sha256": result["right_source_sha256"],
                      "left_source_sha256": result["left_source_sha256"]}))
