"""Normalize saved Native property-route trace into source-bound observations.

The survey and purpose declaration are independent inputs. CARLA's traffic
light state alone cannot establish the lens form or which lane it faces.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from property_bypass_measure import ASSIGNMENT, measure, require


def encode(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def normalize(trace_bytes: bytes, survey_bytes: bytes, purpose_bytes: bytes) -> dict:
    trace = [json.loads(line) for line in trace_bytes.decode().splitlines() if line.strip()]
    survey = json.loads(survey_bytes)
    purpose = json.loads(purpose_bytes)
    require(trace and all(row.get("source_kind") == "original_native_observation" for row in trace),
            "original Native trace required")
    require(survey.get("source_kind") == "original_native_property_survey" and
            survey.get("assignment_id") == ASSIGNMENT,
            "original surveyed map source required")
    require(survey.get("approach_signal_lens_form") == "circular_red_alone" and
            survey.get("approach_signal_facing_source_id"),
            "red-alone lens and facing survey required")
    require(purpose.get("source_kind") == "original_controller_purpose_declaration" and
            purpose.get("assignment_id") == ASSIGNMENT and
            purpose.get("declaration_source_id"),
            "independent controller purpose declaration required")
    require(all(str(row.get("approach_signal_actor_id")) == str(survey.get("approach_signal_actor_id"))
                and str(row.get("cross_signal_actor_id")) == str(survey.get("cross_signal_actor_id"))
                for row in trace), "Native signal identity differs from survey")
    require(all(row.get("vehicle_id") == trace[0].get("vehicle_id") for row in trace),
            "Native vehicle identity changed")
    frames = []
    for i, row in enumerate(trace):
        require(row.get("frame") == i and abs(float(row.get("t_s", -1)) - i / 20) < 1e-8,
                "Native trace is not contiguous 20 Hz")
        approach_state = str(row.get("approach_signal_native_state", "")).rsplit(".", 1)[-1]
        cross_state = str(row.get("cross_signal_native_state", "")).rsplit(".", 1)[-1]
        frames.append({"frame": i, "t_s": i / 20,
                       "vehicle_id": str(row["vehicle_id"]), "zone": row["zone"],
                       "approach_signal": "steady_red_alone" if approach_state == "Red" else
                       "green" if approach_state == "Green" else
                       "yellow" if approach_state == "Yellow" else "unknown",
                       "cross_street_signal": "red" if cross_state == "Red" else
                       "not_red" if cross_state in {"Green", "Yellow"} else "unknown"})
    frame_source = {"assignment_id": ASSIGNMENT, "source_kind": "native_saved_sample",
                    "vehicle_id": str(trace[0]["vehicle_id"]), "frames": frames}
    map_source = {"assignment_id": ASSIGNMENT, "source_kind": "native_saved_sample",
                  "approach_lane_id": survey.get("approach_lane_source"),
                  "intersecting_street_id": survey.get("cross_street_lane_source"),
                  "private_or_public_property_id": survey.get("property_id"),
                  "property_boundary_source_id": survey.get("property_boundary_source_id"),
                  "approach_signal_id": survey.get("approach_signal_actor_id"),
                  "cross_street_signal_id": survey.get("cross_signal_actor_id")}
    purpose_source = {"assignment_id": ASSIGNMENT, "source_kind": "native_saved_sample",
                      "declared_purpose": purpose.get("declared_purpose"),
                      "declaration_source_id": purpose["declaration_source_id"]}
    result = measure(encode(frame_source), encode(map_source), encode(purpose_source))
    result["native_trace_sha256"] = __import__("hashlib").sha256(trace_bytes).hexdigest()
    result["original_survey_sha256"] = __import__("hashlib").sha256(survey_bytes).hexdigest()
    result["original_purpose_sha256"] = __import__("hashlib").sha256(purpose_bytes).hexdigest()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True)
    parser.add_argument("--survey", required=True)
    parser.add_argument("--purpose", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = normalize(Path(args.trace).read_bytes(), Path(args.survey).read_bytes(),
                       Path(args.purpose).read_bytes())
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
