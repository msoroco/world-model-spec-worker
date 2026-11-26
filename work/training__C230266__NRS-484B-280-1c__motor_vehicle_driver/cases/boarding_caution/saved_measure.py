"""Combine sealed capture traces with separate original-source review rows.

The review can record a visibility/position finding. It does not turn those
findings into a claim that the driver actually perceived the pedestrian.
"""

import hashlib
import json
from pathlib import Path

from branch_meter import measure


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(folder, name):
    path = Path(folder) / name
    require(path.is_file(), "Missing required source: " + name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def reviewed_measurement(folder, branch, ego_id, pedestrian_id):
    folder = Path(folder)
    trace = rows(folder, "pedestrian-caution-trace.jsonl")
    review = rows(folder, "pedestrian-source-review.jsonl")
    require(len(trace) == len(review) == 600, "Full capture and separate source review required")
    survey_path = folder / "context-survey.json"
    require(survey_path.is_file(), "Missing required source: context-survey.json")
    survey = json.loads(survey_path.read_text())
    require(survey.get("source_kind") == "original_native_context_survey",
            "Original context survey required")
    joined = []
    for frame, (capture, checked) in enumerate(zip(trace, review)):
        require(str(capture.get("ego_actor_id")) == str(ego_id) and
                str(capture.get("pedestrian_actor_id")) == str(pedestrian_id) and
                ego_id != pedestrian_id,
                "Captured actor identity changed")
        require(checked.get("source_kind") == "original_saved_source_review",
                "Independent original-source review required")
        require(checked.get("frame") == capture.get("frame") == frame and
                checked.get("native_frame") == capture.get("native_frame") and
                checked.get("video_frame") == capture.get("video_frame"),
                "Capture/review frame join failed")
        require(capture.get("context_survey_sha256") == sha(survey_path),
                "Context survey binding changed")
        require(checked.get("context_survey_sha256") == sha(survey_path),
                "Review survey binding changed")
        require(type(checked.get("line_of_sight_clear")) is bool and
                type(checked.get("branch_position_evidenced")) is bool,
                "Original visibility/position finding missing")
        observed = checked.get("driver_observed_pedestrian")
        require(observed is None or type(observed) is bool,
                "Driver-observation review type invalid")
        require(not observed or checked.get("driver_observation_source"),
                "Actual observation provenance missing")
        row = dict(capture)
        for key in ("line_of_sight_clear", "branch_position_evidenced",
                    "driver_observed_pedestrian", "driver_observation_source"):
            row[key] = checked.get(key)
        joined.append(row)
    packet = {"format": "worker-pedestrian-caution-branch-source-v1",
              "law_id": "NRS-484B-280-1c", "cell_id": "C230266",
              "actor": "motor_vehicle_driver", "branch": branch,
              "ego_id": ego_id, "pedestrian_id": pedestrian_id,
              "pedestrian_classification_source": survey.get("pedestrian_classification_source"),
              "survey": survey, "trace": joined,
              "trace_sha256": hashlib.sha256(json.dumps(joined, sort_keys=True,
                                                    separators=(",", ":")).encode()).hexdigest()}
    return {"measurement": measure(packet),
            "sources": {name: sha(folder / name) for name in
                        ("pedestrian-caution-trace.jsonl", "pedestrian-source-review.jsonl",
                         "context-survey.json")}}
