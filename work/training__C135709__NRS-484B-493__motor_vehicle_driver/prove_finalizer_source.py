"""Exercise saved-only finalizer with source-shaped roles and controlled negatives."""
import copy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "native"))
from finalize import analyze, finalize
from geometry import open_drive
from prove_one_way_saved_measure import sample
from prove_source_review import prepare
from one_way_saved_measure import CAMERAS


def lines(rows):
    return "\n".join(json.dumps(row, separators=(",", ":")) for row in rows) + "\n"


def fixture(path, condition, side):
    path.mkdir(parents=True)
    prepare(path)
    (path / "road.xodr").write_text(open_drive())
    packet, context = sample(side)
    context["source_kind"] = "native_saved_sample"
    context["road_id"] = "1"
    context["device_governs_road_id"] = "1"
    context["map_source_sha256"] = hashlib.sha256((path / "road.xodr").read_bytes()).hexdigest()
    (path / "road-context.json").write_text(json.dumps(context) + "\n")
    poses = packet["frames"]
    mapping = [{"video_frame": row["video_frame"], "native_frame": row["native_frame"],
                "carla_frame": row["native_frame"],
                "time_s": row["time_s"], "camera_native_frames": row["camera_native_frames"]}
               for row in poses]
    (path / "vehicle-pose.jsonl").write_text(lines(poses))
    (path / "video_frames.jsonl").write_text(lines(mapping))
    (path / "trace.jsonl").write_text(lines([{"frame": row["native_frame"],
        "time_s": row["time_s"], "position": {"x": 20, "y": 1.5 if side == "left" else -1.5, "z": 0},
        "speed_mps": row["speed_mps"]} for row in poses]))
    for camera in CAMERAS:
        (path / (camera + ".mkv")).write_text("synthetic video role placeholder\n")
    case = "training__C135709__NRS-484B-493__motor_vehicle_driver__" + condition
    config = {"case_id": case, "selected_case_id": case, "law_id": "NRS-484B-493",
              "cell_id": "C135709", "rate_hz": 20, "duration_s": 30,
              "parking_side": side, "recording_description": {"channels": []}}
    (path / "config.json").write_text(json.dumps(config) + "\n")
    (path / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
    return case


def rejects(path, expected):
    try:
        analyze(path)
    except ValueError as error:
        if expected in str(error):
            return
        raise
    raise AssertionError("Expected rejection: " + expected)


def main(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    outcomes = {}
    for condition, side in (("controlled_1", "right"), ("controlled_2", "left")):
        path = root / condition
        fixture(path, condition, side)
        before = {p.relative_to(path): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in path.rglob("*") if p.is_file()}
        measurement = analyze(path)
        expected = "fully_right_governed_frames" if side == "right" else "fully_left_governed_frames"
        if measurement["measurement"][expected] != list(range(200, 400)):
            raise AssertionError("Saved side differs")
        report = finalize(path, path / "analysis-report.json")
        if set(report["measurements"]) != {"notice_context", "stationary_side"}:
            raise AssertionError("Selected measurement keys differ")
        after = {p.relative_to(path): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in path.rglob("*") if p.is_file() and p.relative_to(path) in before}
        if before != after:
            raise AssertionError("Original source changed")
        outcomes[condition] = {"side": side, "stationary_frames": 200,
                               "source_preserved": True}
        bad = root / (condition + "-missing-authority")
        import shutil
        shutil.copytree(path, bad, ignore=shutil.ignore_patterns("channels", "result.json", "analysis-report.json"))
        (bad / "authority-review/device-authority.json").unlink()
        rejects(bad, "Missing required source: authority-review/device-authority.json")
        if condition == "controlled_2":
            for label, source, key in (("absent_notice", "device-content", "notice_prohibits_left_standing_or_parking"),
                                       ("two_way", "one-way-designation", "roadway_is_one_way")):
                variant = root / label
                shutil.copytree(bad, variant)
                shutil.copy2(path / "authority-review/device-authority.json",
                             variant / "authority-review/device-authority.json")
                review = variant / "authority-review" / (source + ".json")
                value = json.loads(review.read_text())
                value[key] = False
                review.write_text(json.dumps(value) + "\n")
                rejects(variant, "Required activation unverified: " + source)
    print(json.dumps({"passed": True, "outcomes": outcomes,
        "negative_controls": ["missing_authority", "absent_notice", "two_way"],
        "original_authority_claimed": False, "legal_result_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: prove_finalizer_source.py SCRATCH_OUTPUT")
    main(sys.argv[1])
