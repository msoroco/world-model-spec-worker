"""Read original saved crosswalk frames without changing their bytes."""

import argparse
import hashlib
import json
from pathlib import Path

from crosswalk_delivery import audit, measure, validate_source


def analyze(attempt, *, expected_relation):
    attempt = Path(attempt)
    context = attempt / "reviewed-crosswalk-source.json"
    frames_path = attempt / "channels" / "reverse-body-crosswalk.jsonl"
    if not context.is_file():
        raise ValueError("Missing required source: reviewed-crosswalk-source.json")
    if not frames_path.is_file():
        raise ValueError("Missing required source: channels/reverse-body-crosswalk.jsonl")
    source = json.loads(context.read_text())
    validate_source(source["map_packet"])
    actual_sha = hashlib.sha256(frames_path.read_bytes()).hexdigest()
    if actual_sha != source.get("frames_sha256"):
        raise ValueError("saved original frame hash differs")
    frames = [json.loads(line) for line in frames_path.read_text().splitlines()]
    if any(frame.get("crosswalk_polygon_xy") != source["map_packet"]["crosswalk_polygon_xy"]
           for frame in frames):
        raise ValueError("saved frame crosswalk differs from reviewed original map polygon")
    measured = measure(frames, source_id=source["source_id"],
                       map_sha256=source["map_packet"]["map_sha256"],
                       crosswalk_source=source["map_packet"]["crosswalk_source"],
                       vehicle_actor_id=source["vehicle_actor_id"])
    physical = audit(measured, expected_relation=expected_relation)
    return {"measurements": {"crosswalk_relation": physical},
            "source_sha256": actual_sha, "legal_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-relation", choices=("disjoint", "contact", "overlap"), required=True)
    args = parser.parse_args()
    report = analyze(args.attempt, expected_relation=args.expected_relation)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
