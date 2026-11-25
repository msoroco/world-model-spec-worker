"""Independent paired sidewalk fixture clearance comparison."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "native"))
from finalize import analyze


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(attempt_a, attempt_b, processing_a, processing_b, diagnostic=False):
    a, b = Path(attempt_a).resolve(), Path(attempt_b).resolve()
    pa, pb = (json.loads(Path(path).read_text()) for path in (processing_a, processing_b))
    prefix = "training__C150668__LVMC-11-52-130-A5__motor_vehicle_driver__"
    if [pa.get("case_id"), pb.get("case_id")] != [prefix + "probe_1", prefix + "probe_2"]:
        raise ValueError("Exact comparison cases differ")
    if not all(p.get("passed") is True and p.get("recorded_only") is True for p in (pa, pb)):
        raise ValueError("Recorded-only processing proof missing")
    for source in ("road.xodr", "fixture-inventory.json"):
        if sha(a / source) != sha(b / source):
            raise ValueError("Fixed physical context differs: " + source)
    for role in ("fixture-identity", "fixture-geometry", "sidewalk-geometry", "front-orientation"):
        for suffix in (".json", ".source.txt"):
            source = "fixture-review/" + role + suffix
            if sha(a / source) != sha(b / source):
                raise ValueError("Fixed reviewed fixture source differs: " + source)
    configs = [json.loads((path / "config.json").read_text()) for path in (a, b)]
    for field in ("law_id", "cell_id", "actor", "rate_hz", "duration_s",
                  "cameras", "source_actor_ids", "required_atoms", "brake_margin_m"):
        if configs[0].get(field) != configs[1].get(field):
            raise ValueError("Fixed comparison configuration differs: " + field)
    if [config.get("stop_case") for config in configs] != ["outside", "side_band"]:
        raise ValueError("Declared stop-station contrast differs")
    measured = [analyze(path) for path in (a, b)]
    outside = measured[0]["measurement"]
    inside = measured[1]["measurement"]
    if outside["within_five_foot_side_band_at_rest"] or not inside[
            "within_five_foot_side_band_at_rest"]:
        raise ValueError("Measured side-band contrast absent")
    if diagnostic and any(json.loads((path / "acquisition-provenance.json").read_text()).get(
            "provenance_kind") != "synthetic_fixture" for path in (a, b)):
        raise ValueError("Diagnostic comparison requires identified CPU fixtures")
    return {"format": "c150668-comparison-audit-v1",
            "case_ids": [item["case_id"] for item in measured],
            "diagnostic_fixture": diagnostic,
            "fixed_map_sha256": sha(a / "road.xodr"),
            "deliberate_difference": "requested_and_measured_side_clearance",
            "outside_clearance_m": outside["side_clearance_m_range_at_rest"],
            "inside_clearance_m": inside["side_clearance_m_range_at_rest"],
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False}


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
