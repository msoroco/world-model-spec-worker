"""CPU diagnostic proof for 600-frame, source-bound stop/yield observations."""
import hashlib
import json
from pathlib import Path

from stop_yield_saved_measure import ASSIGNMENT, ASSIGNMENT_SHA, WITNESS_SHA, measure


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def fixture(inside_at_entry=True, officer=False, counterpart_control="none"):
    controls = {
        "assignment_id": ASSIGNMENT,
        "source_kind": "synthetic_native_sample",
        "road_kind": "non_through_highway",
        "subject_control": "stop_sign",
        "subject_entrance_sign_governs": True,
        "counterpart_control": counterpart_control,
        "stop_reference": "stop_line",
    }
    frames = []
    for i in range(600):
        frames.append({
            "frame": i, "t_s": i / 20,
            "subject_id": "ego", "counterpart_id": "other",
            "subject_speed_mps": 0.0 if 160 <= i < 180 else 3.0,
            "subject_front_before_reference": i < 190,
            "subject_inside": 200 <= i < 260,
            "counterpart_inside": (180 <= i < 240) if inside_at_entry else (270 <= i < 320),
            "officer_controlling": officer and 180 <= i < 260,
            "signal_controlling": False,
        })
    raw = {"assignment_id": ASSIGNMENT, "source_kind": "synthetic_native_sample", "subject_id": "ego", "counterpart_id": "other", "frames": frames}
    return raw, controls


def main():
    root = Path(__file__).resolve().parents[2]
    assignment = root / "inputs" / ASSIGNMENT / "assignment.json"
    witness = root / "inputs" / ASSIGNMENT / "witnesses.json"
    assert hashlib.sha256(assignment.read_bytes()).hexdigest() == ASSIGNMENT_SHA
    assert hashlib.sha256(witness.read_bytes()).hexdigest() == WITNESS_SHA
    a = json.loads(assignment.read_text())
    assert "within the intersection" in a["law"]["text"]
    assert "police officer" in a["law"]["text"]
    assert "through highway" in a["law"]["text"]
    positive, controls = fixture()
    p = measure(canonical(positive), canonical(controls))
    assert p["duration_s"] == 30 and p["subject_entry_frame"] == 200
    assert p["subject_exit_frame"] == 260
    assert p["pre_entry_near_zero_frames_before_reference"] == list(range(160, 180))
    assert p["counterpart_not_obligated_to_stop_or_yield"] is True
    assert p["counterpart_inside_at_entry"] is True
    assert p["counterpart_inside_during_crossing_frames"] == list(range(200, 240))
    assert p["legal_result"] is None
    outside, c = fixture(inside_at_entry=False)
    q = measure(canonical(outside), canonical(c))
    assert q["counterpart_inside_at_entry"] is False and q["counterpart_inside_during_crossing_frames"] == []
    controlled, c = fixture(officer=True)
    r = measure(canonical(controlled), canonical(c))
    assert r["officer_or_signal_control_frames"] == list(range(180, 260))
    obligated, c = fixture(counterpart_control="stop_sign")
    s = measure(canonical(obligated), canonical(c))
    assert s["counterpart_not_obligated_to_stop_or_yield"] is False
    missing, c = fixture()
    missing["frames"].pop(155)
    last = dict(missing["frames"][-1])
    last["frame"] = 600
    last["t_s"] = 30.0
    missing["frames"].append(last)
    try:
        measure(canonical(missing), canonical(c))
        raise AssertionError("missing frame accepted")
    except ValueError as e:
        assert str(e) == "noncontiguous 20 Hz frames"
    bad, c = fixture()
    c["subject_entrance_sign_governs"] = False
    try:
        measure(canonical(bad), canonical(c))
        raise AssertionError("ungoverned sign accepted")
    except ValueError as e:
        assert str(e) == "subject sign does not govern entrance"
    print(json.dumps({"passed": True, "assignment_sha256": ASSIGNMENT_SHA, "witness_sha256": WITNESS_SHA, "positive_source_sha256": p["source_sha256"], "positive_controls_sha256": p["control_inventory_sha256"], "outside_source_sha256": q["source_sha256"], "officer_source_sha256": r["source_sha256"], "obligated_controls_sha256": s["control_inventory_sha256"], "checks": ["30s_contiguous_20hz", "pre_entry_cessation", "other_inside_at_entry", "other_outside_counterexample", "officer_exception_presence", "counterpart_obligation", "missing_frame_rejection", "ungoverned_sign_rejection"]}, sort_keys=True))


if __name__ == "__main__":
    main()
