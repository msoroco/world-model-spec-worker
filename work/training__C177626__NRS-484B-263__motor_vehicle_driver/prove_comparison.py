"""Synthetic original-shaped comparison audit probes; never a capture receipt."""
from copy import deepcopy
import json
from pathlib import Path
import runpy
import sys
import tempfile

base = Path(__file__).resolve().parent
sys.path.insert(0, str(base / "native"))
sys.path.insert(0, str(base))
from acquisition import bind_original
from audit_comparison import CASE_IDS, POLICIES, compare, inspect

fixture = runpy.run_path(str(base / "native" / "prove_acquisition.py"))
rows = fixture["rows"]
cameras = fixture["cameras"]
context = fixture["context"]


def write(root, case, policy):
    root.mkdir()
    ctx = {**context, "case_id": case}
    data = {"result.json": {"case_id": case, "provenance_kind": "native",
                            "legal_verdict_claimed": False,
                            "physical_acceptance_claimed": False},
            "authored-context.json": ctx,
            "source-bound-measurements.json": bind_original(rows, cameras, ctx, policy)}
    for name, value in data.items():
        (root / name).write_text(json.dumps(value) + "\n")
    for name, value in (("native_samples.jsonl", rows), ("camera_frames.jsonl", cameras),
                        ("video_frames.jsonl", [{"video_frame": i, "native_frame": 1000 + i}
                                                for i in range(600)])):
        (root / name).write_text("".join(json.dumps(row) + "\n" for row in value))


def reject(call, phrase):
    try:
        call()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


with tempfile.TemporaryDirectory() as tmp:
    a, b = Path(tmp) / "a", Path(tmp) / "b"
    write(a, CASE_IDS[0], POLICIES[0])
    write(b, CASE_IDS[1], POLICIES[1])
    source_a = inspect(a, CASE_IDS[0], POLICIES[0])
    source_b = inspect(b, CASE_IDS[1], POLICIES[1])
    report = compare(source_a, source_b)
    assert report["passed"] is True and report["legal_verdict"] is None
    broken = deepcopy(source_b)
    broken["map_sha256"] = "f" * 64
    reject(lambda: compare(source_a, broken), "map_sha256")
    broken = deepcopy(source_b)
    broken["initial_traffic"]["near"]["center_xy_m"] = [0, 0]
    reject(lambda: compare(source_a, broken), "initial_traffic")
    broken = deepcopy(source_b)
    broken["policy"] = "earlier_yield"
    reject(lambda: compare(source_a, broken), "policy difference")
    (b / "camera_frames.jsonl").write_text("\n".join(
        (b / "camera_frames.jsonl").read_text().splitlines()[:599]) + "\n")
    reject(lambda: inspect(b, CASE_IDS[1], POLICIES[1]), "600-frame")
    (b / "camera_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in cameras))
    m = json.loads((b / "source-bound-measurements.json").read_text())
    m["measurements"]["controller_yield_request_frames"] += 1
    (b / "source-bound-measurements.json").write_text(json.dumps(m) + "\n")
    reject(lambda: inspect(b, CASE_IDS[1], POLICIES[1]), "differ from original")
    (b / "source-bound-measurements.json").write_text(json.dumps(bind_original(rows, cameras,
        {**context, "case_id": CASE_IDS[1]}, POLICIES[1])) + "\n")
    (b / "result.json").unlink()
    reject(lambda: inspect(b, CASE_IDS[1], POLICIES[1]), "Missing original source")
print("PASS: independent exact-case saved comparison, 6 missing/changed-source negatives")
