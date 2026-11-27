"""Exercise the saved-only finalizer against original-shaped synthetic sources."""
import json
from pathlib import Path
import runpy
import sys
import tempfile

base = Path(__file__).resolve().parent
sys.path.insert(0, str(base))
sys.path.insert(0, str(base / "native"))
sys.path.insert(0, str(Path("runtime/scenario_pipeline").resolve()))
from finalize import finalize
from audit_comparison import CASE_IDS, VIEWS

fixture = runpy.run_path(str(base / "native/prove_acquisition.py"))
rows, cameras = fixture["rows"], fixture["cameras"]
rows = [{**row, "native_elapsed_s": row["time_s"]} for row in rows]


def write_lines(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in records))


def reject(call, phrase):
    try:
        call()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("Expected rejection: " + phrase)


with tempfile.TemporaryDirectory() as temp:
    root = Path(temp) / "attempt"
    root.mkdir()
    config = {"case_id": CASE_IDS[0], "recording_description": {"channels": [
        {"name": name, "unit": "structured"} for name in (
            "st.controlled_access", "drv.entering_intersection", "drv.lane_change",
            "drv.approaching", "drv.time_to_conflict", "rel.surface_gap",
            "drv.yields_to", "drv.hard_deceleration")]}}
    (root / "config.json").write_text(json.dumps(config) + "\n")
    (root / "authored-context.json").write_text(json.dumps({**fixture["context"],
        "case_id": CASE_IDS[0]}) + "\n")
    (root / "capture-seal.json").write_text('{"diagnostic_fixture": true}\n')
    write_lines(root / "native_samples.jsonl", rows)
    write_lines(root / "camera_frames.jsonl", cameras)
    write_lines(root / "entry_history.jsonl", [{"frame": 1000 + i,
        "time_s": i / 20, "position_m": row["ego"]["center_xy_m"],
        "road_id": row["ego"]["road_id"]} for i, row in enumerate(rows)])
    write_lines(root / "trace.jsonl", [{"frame": 1000 + i} for i in range(600)])
    write_lines(root / "video_frames.jsonl", [{"video_frame": i,
        "native_frame": 1000 + i, "time_s": i / 20} for i in range(600)])
    write_lines(root / "capture/evidence.jsonl", [{"original_frame": 1000 + i}
        for i in range(600)])
    for view in VIEWS:
        (root / (view + ".mkv")).write_bytes(b"synthetic-placeholder")
    report = finalize(root, Path(temp) / "analysis.json")
    assert report["original_native_source"] is False
    result = json.loads((root / "result.json").read_text())
    assert result["provenance_kind"] == "synthetic_fixture"
    assert result["measured_values"]["frames"] == 600
    assert result["legal_verdict_claimed"] is False
    (root / "result.json").unlink()
    (root / "driver_reference.mkv").unlink()
    reject(lambda: finalize(root, Path(temp) / "failure.json"),
           "Missing required source: driver_reference.mkv")
    (root / "driver_reference.mkv").write_bytes(b"synthetic-placeholder")
    lines = (root / "entry_history.jsonl").read_text().splitlines()
    broken = json.loads(lines[40]); broken["frame"] += 1
    lines[40] = json.dumps(broken)
    (root / "entry_history.jsonl").write_text("\n".join(lines) + "\n")
    reject(lambda: finalize(root, Path(temp) / "failure.json"),
           "original actor, camera, trace, frame and event join differs")
print("PASS: saved-only synthetic finalizer and missing-view/frame-join negatives")
