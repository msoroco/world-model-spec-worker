"""Saved-only projection of sealed original Native intersection observations.

This report carries raw geometric and motion measurements. It makes no legal
immediate-hazard, cautiousness, right-of-way or physical-visibility claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_witness import measure


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _original(attempt, name, inventory):
    item = inventory.get(name)
    path = attempt / name
    if (not isinstance(item, dict) or item.get("kind") != "original_native" or
            not path.is_file() or item.get("sha256") != _sha(path)):
        raise ValueError("missing or stale original Native source: " + name)
    return path


def analyze(attempt):
    attempt = Path(attempt).resolve()
    config = json.loads((attempt / "config.json").read_text())
    selected = config.get("selected_case_id")
    cases = {item["case_id"]: item for item in json.loads(
        Path(__file__).with_name("case-specs.json").read_text())["cases"]}
    if selected not in cases:
        raise ValueError("selected exact case absent from source-bound plan")
    spec = cases[selected]
    inventory = json.loads((attempt / "acquisition.json").read_text())
    history_path = _original(attempt, "original-history.json", inventory)
    frame_map_path = _original(attempt, "video_frames.jsonl", inventory)
    packet = json.loads(history_path.read_text())
    if packet.get("case_id") != selected or packet.get("control_context") != spec["control_context"]:
        raise ValueError("original history differs from selected exact case")
    frames = [json.loads(line) for line in frame_map_path.read_text().splitlines() if line.strip()]
    if len(frames) != 900 or len(packet.get("frames", [])) != 900:
        raise ValueError("full original frame inventory required")
    for i, (row, sample) in enumerate(zip(frames, packet["frames"])):
        if (row.get("video_frame") != i or row.get("carla_frame") != sample.get("native_frame") or
                abs(row.get("time_s", -1) - sample.get("time_s", -2)) > .001):
            raise ValueError("original Native/video frame join differs")
    measured = measure(packet, spec["control_context"], spec["counterpart_relation"])
    return {
        "format": "worker-analysis-report",
        "case_id": selected,
        "measurements": {"intersection_approach": {
            "value": measured,
            "method": "native_witness.measure",
            "sources": {"original-history.json": _sha(history_path),
                        "video_frames.jsonl": _sha(frame_map_path)}}},
        "analysis_complete": True,
        "legal_verdict_claimed": False,
        "physical_acceptance_claimed": False,
        "limitations": [
            "Immediate hazard and due caution require independent original-source review.",
            "Actual pixels and physical completion require separate original media and motion audits."
        ]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(analyze(args.attempt), indent=2) + "\n")


if __name__ == "__main__":
    main()
