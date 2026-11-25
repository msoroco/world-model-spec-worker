"""Independent source comparison of the two roundabout entry conditions."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "native"))
from finalize import analyze, rows


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(attempt_a, attempt_b, processing_a, processing_b, diagnostic=False):
    a, b = Path(attempt_a).resolve(), Path(attempt_b).resolve()
    pa, pb = json.loads(Path(processing_a).read_text()), json.loads(Path(processing_b).read_text())
    expected = "training__C239014__LVMC-11-43-010-B__motor_vehicle_driver__selected_a60a4f45__"
    if pa.get("case_id") != expected + "condition_a" or pb.get("case_id") != expected + "condition_b":
        raise ValueError("Exact comparison cases differ")
    if not all(p.get("passed") is True and p.get("recorded_only") is True for p in (pa, pb)):
        raise ValueError("Recorded-only processing proof missing")
    if sha(a / "road.xodr") != sha(b / "road.xodr"):
        raise ValueError("Fixed roundabout geometry differs")
    config_a, config_b = (json.loads((path / "config.json").read_text()) for path in (a, b))
    for field in ("law_id", "cell_id", "actor", "rate_hz", "duration_s",
                  "cameras", "source_actor_ids", "required_atoms"):
        if config_a.get(field) != config_b.get(field):
            raise ValueError("Fixed comparison configuration differs: " + field)
    if (config_a["entry_release_s"], config_b["entry_release_s"]) != (17.0, 12.5):
        raise ValueError("Declared entry timing contrast differs")
    intent_a = rows(a / "control-intent.jsonl")
    intent_b = rows(b / "control-intent.jsonl")
    if len(intent_a) != len(intent_b) or len(intent_a) != 600:
        raise ValueError("Fixed traffic schedule lacks 600 frames")
    for first, second in zip(intent_a, intent_b):
        for role in ("lead", "follower"):
            x, y = first["controls"][role], second["controls"][role]
            for field in ("target_xy_m", "target_speed_mps"):
                if x.get(field) != y.get(field):
                    raise ValueError("Circulating traffic request differs: " + role)
    measured_a, measured_b = analyze(a), analyze(b)
    if measured_a["first_entry_frame"] <= measured_b["first_entry_frame"]:
        raise ValueError("Controlled entry ordering did not differ as requested")
    if diagnostic and any(json.loads((path / "acquisition-provenance.json").read_text()).get(
            "provenance_kind") != "synthetic_fixture" for path in (a, b)):
        raise ValueError("Diagnostic comparison requires CPU fixtures")
    return {"format": "c239014-comparison-audit-v1",
            "case_ids": [measured_a["case_id"], measured_b["case_id"]],
            "diagnostic_fixture": diagnostic, "fixed_map_sha256": sha(a / "road.xodr"),
            "fixed_traffic_request_frames": 600,
            "deliberate_difference": "entry_release_time",
            "entry_frames": [measured_a["first_entry_frame"], measured_b["first_entry_frame"]],
            "traffic_near_at_entry": [measured_a["traffic_near_at_entry"],
                                      measured_b["traffic_near_at_entry"]],
            "legal_verdict_claimed": False, "physical_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for option in ("attempt-a", "attempt-b", "processing-a", "processing-b", "output"):
        parser.add_argument("--" + option, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    value = compare(args.attempt_a, args.attempt_b, args.processing_a,
                    args.processing_b, args.diagnostic)
    Path(args.output).write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps(value, sort_keys=True))
