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
    ids = [pa.get("case_id"), pb.get("case_id")]
    pairs = {(1, 2): "side_clearance", (2, 3): "direct_front",
             (2, 4): "traffic_conflict", (2, 5): "police_direction",
             (2, 6): "device_direction", (1, 7): "at_five_feet"}
    pair = next((key for key in pairs if ids == [prefix + "probe_" + str(n) for n in key]), None)
    if pair is None:
        raise ValueError("Exact comparison cases differ")
    if not all(p.get("passed") is True and p.get("recorded_only") is True for p in (pa, pb)):
        raise ValueError("Recorded-only processing proof missing")
    for source in ("road.xodr",):
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
    expected_stops = ("outside", "at_five_feet") if pair == (1, 7) else (
        ("outside", "side_band") if pair == (1, 2) else (
        "side_band", "front" if pair == (2, 3) else "side_band")
        )
    if tuple(config.get("stop_case") for config in configs) != expected_stops:
        raise ValueError("Declared stop-station contrast differs")
    expected_modes = ("none", "none") if pair[1] <= 3 or pair == (1, 7) else (
        "none", pairs[pair])
    if tuple(config.get("exception_mode") for config in configs) != expected_modes:
        raise ValueError("Declared exception contrast differs")
    measured = [analyze(path) for path in (a, b)]
    outside = measured[0]["measurement"]
    inside = measured[1]["measurement"]
    if pair in ((1, 2), (1, 7)):
        if outside["within_five_foot_side_band_at_rest"] or not inside[
                "within_five_foot_side_band_at_rest"]:
            raise ValueError("Measured side-band contrast absent")
        if pair == (1, 7) and inside["side_clearance_m_range_at_rest"] != [1.524, 1.524]:
            raise ValueError("Exact five-foot boundary absent")
    elif pair == (2, 3):
        if not outside["within_five_foot_side_band_at_rest"] or inside[
                "directly_in_front_frame_count_at_rest"] < 100:
            raise ValueError("Measured direct-front contrast absent")
    else:
        key = {4: "traffic_conflict_reviewed", 5: "police_stop_direction_reviewed",
               6: "device_stop_direction_reviewed"}[pair[1]]
        if measured[0]["context"][key] or not measured[1]["context"][key] or not all(
                item["measurement"]["within_five_foot_side_band_at_rest"] for item in measured):
            raise ValueError("Measured exception-source contrast absent")
    if diagnostic and any(json.loads((path / "acquisition-provenance.json").read_text()).get(
            "provenance_kind") != "synthetic_fixture" for path in (a, b)):
        raise ValueError("Diagnostic comparison requires identified CPU fixtures")
    return {"format": "c150668-comparison-audit-v1",
            "case_ids": [item["case_id"] for item in measured],
            "diagnostic_fixture": diagnostic,
            "fixed_map_sha256": sha(a / "road.xodr"),
            "deliberate_difference": pairs[pair],
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
