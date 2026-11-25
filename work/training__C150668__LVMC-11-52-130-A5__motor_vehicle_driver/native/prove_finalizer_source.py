"""Exercise saved-only meter with source-shaped diagnostic and missing-role controls."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

from finalize import analyze
from measure_fixture import CAMERAS, FRAMES
from prove_source_review import build, put

ASSIGNMENT = "training__C150668__LVMC-11-52-130-A5__motor_vehicle_driver"


def lines(rows):
    return "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)


def fixture(path, suffix, stop_x):
    build(path)
    case = ASSIGNMENT + "__" + suffix
    put(path / "config.json", {"case_id": case, "selected_case_id": case,
        "cell_id": "C150668", "law_id": "LVMC-11-52-130-A5",
        "rate_hz": 20, "duration_s": 30,
        "recording_description": {"channels": [], "limitations": ["CPU diagnostic only"]}})
    poses, frame_map, trace = [], [], []
    for i in range(FRAMES):
        native = 5000 + i
        x = -50 + (stop_x + 50) * i / 100 if i < 100 else stop_x
        camera_frames = {name: native for name in CAMERAS}
        footprint = {"min_x": x - 2, "max_x": x + 2,
                     "min_y": -2.5, "max_y": -0.3}
        common = {"video_frame": i, "native_frame": native,
                  "time_s": i / 20, "camera_native_frames": camera_frames}
        frame_map.append(dict(common, carla_frame=native))
        poses.append(dict(common, observed_vehicle_speed_mps=3.0 if i < 100 else 0.0,
                          vehicle_footprint_m=footprint))
        trace.append({"frame": native, "time_s": i / 20,
                      "position": {"x": x, "y": -1.75, "z": 0},
                      "speed_mps": 3.0 if i < 100 else 0.0})
    (path / "vehicle-poses.jsonl").write_text(lines(poses))
    (path / "video_frames.jsonl").write_text(lines(frame_map))
    (path / "trace.jsonl").write_text(lines(trace))
    for name in CAMERAS:
        (path / (name + ".mkv")).write_text("Synthetic CPU role placeholder\n")
    return case


def reject(path, expected):
    try:
        analyze(path)
    except ValueError as error:
        if expected in str(error):
            return str(error)
        raise
    raise AssertionError("Saved meter accepted defective source: " + expected)


def main(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    result = {}
    for suffix, x, expected in (("probe_1", 10, False), ("probe_2", 5, True)):
        good = root / suffix
        fixture(good, suffix, x)
        before = {str(p.relative_to(good)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in good.rglob("*") if p.is_file()}
        data = analyze(good)
        assert data["measurement"]["within_five_foot_side_band_at_rest"] is expected
        after = {str(p.relative_to(good)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in good.rglob("*") if p.is_file()}
        assert before == after
        bad = root / (suffix + "-missing-fixture-identity")
        shutil.copytree(good, bad)
        (bad / "fixture-review/fixture-identity.json").unlink()
        result[suffix] = {"within_side_band": expected,
                          "source_preserved": True,
                          "missing_identity_rejected": reject(bad, "Missing required source")}
    original = root / "original-proxy"
    shutil.copytree(root / "probe_2", original)
    (original / "acquisition-provenance.json").unlink()
    result["original_proxy_rejected"] = reject(original, "Generic fixture proxy")
    return {"passed": True, "diagnostic_only": True,
            "original_fixture_observed": False, "outcomes": result}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: prove_finalizer_source.py SCRATCH")
    print(json.dumps(main(sys.argv[1]), indent=2))
