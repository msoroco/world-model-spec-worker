"""Finalize original frame-joined body geometry for a surveyed left turn."""

import argparse
import json
from pathlib import Path

from body_position import measure_frame
from route_survey import load_survey


def finalize(survey_path, survey_sha256, body_path, output_path):
    survey = load_survey(survey_path, survey_sha256)
    body_path = Path(body_path)
    if not body_path.is_file():
        raise ValueError("Missing original body stream")
    rows = [json.loads(line) for line in body_path.read_text().splitlines() if line]
    if not rows:
        raise ValueError("Empty original body stream")
    seen = set()
    phases = set()
    observations = []
    for row in rows:
        measured = measure_frame(row, survey)
        frame = measured["frame"]
        if frame in seen:
            raise ValueError("Duplicate original frame")
        seen.add(frame)
        phases.add(measured["phase"])
        observations.append(measured)
    if phases != {"approach", "entry", "departure"}:
        raise ValueError("Original turn phases are incomplete")
    if [x["frame"] for x in observations] != sorted(seen):
        raise ValueError("Original frame order changed")
    report = {
        "format": "worker-original-turn-position-measurement",
        "source": "Native XODR surveyed route and original full-body corners",
        "survey_sha256": survey_sha256,
        "original_body_path": body_path.name,
        "frames": len(observations),
        "phases": sorted(phases),
        "observations": observations,
        "legal_conclusion": None,
        "limitations": "Public highway status, directions, legal proximity and original camera visibility need source review",
    }
    Path(output_path).write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--survey", required=True)
    parser.add_argument("--survey-sha256", required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps({key: value for key, value in finalize(args.survey, args.survey_sha256, args.body, args.output).items() if key != "observations"}, sort_keys=True))
