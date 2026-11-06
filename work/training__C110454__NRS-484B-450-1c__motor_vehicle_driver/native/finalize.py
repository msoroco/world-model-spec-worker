"""Source-bound saved parking relation report; full Core/video package remains pending."""
import argparse
import hashlib
import json
from pathlib import Path
from measure import measure


def finalize(attempt: Path, output: Path) -> dict:
    source = attempt / "native_samples.jsonl"
    if not source.is_file():
        raise ValueError("Missing required source: native_samples.jsonl")
    config_path = attempt / "config.json"
    if not config_path.is_file():
        raise ValueError("Missing required source: config.json")
    config = json.loads(config_path.read_text())
    if config.get("duration_s") != 24 or config.get("rate_hz") != 20:
        raise ValueError("Exact capture duration/rate differs")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    value = measure(source, digest)
    expected = {"probe_a": "outside_intersection", "probe_b": "within_intersection"}
    suffix = config.get("case_suffix")
    if suffix not in expected or value["parking_relation"] != expected[suffix]:
        raise ValueError("Measured parking relation differs from requested probe")
    report = {"format": "c110454-450-1c-saved-measurement-v1",
              "case_id": config["case_id"], "candidate_id": config["candidate_id"],
              "measurements": {"intersection_parking_footprint": {
                  "value": value, "method": "measure_saved_footprint",
                  "sources": {"native_samples.jsonl": digest}}},
              "scope": "saved sampled geometry only; Core/video/independent acceptance pending"}
    with output.open("x") as target:
        json.dump(report, target, indent=2)
        target.write("\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--attempt", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(finalize(a.attempt, a.output)))
