"""Saved-only measurements of the C125714 crossing; no legal evaluator."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from crossing_audit import measure


SOURCES = ("intersection-context.json", "ego-body-history.jsonl",
           "other-body-history.jsonl")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _source(attempt, acquisition, name):
    path = attempt / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    item = acquisition.get(name, {})
    if item.get("kind") != "original_native" or item.get("sha256") != _sha(path):
        raise ValueError("Missing or stale original Native source: " + name)
    return path


def _rows(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError("Empty original Native history: " + path.name)
    return rows


def crossing_entry_measurement(trace):
    """Measure body entry and clearance from joined source-bound frames."""
    return measure(trace)


def build_report(attempt):
    attempt = Path(attempt)
    acquisition = json.loads((attempt / "acquisition.json").read_text())
    sources = {name: _source(attempt, acquisition, name) for name in SOURCES}
    context = json.loads(sources["intersection-context.json"].read_text())
    provenance_path = attempt / "acquisition-provenance.json"
    if not provenance_path.is_file():
        raise ValueError("Missing acquisition provenance")
    provenance = json.loads(provenance_path.read_text())
    if provenance.get("provenance_kind") == "native":
        reviewed_path = _source(attempt, acquisition, "reviewed-context.json")
        map_path = _source(attempt, acquisition, "road.xodr")
        reviewed_hash = _sha(reviewed_path)
        if (context.get("reviewed_context_sha256") != reviewed_hash or
                provenance.get("reviewed_context_sha256") != reviewed_hash):
            raise ValueError("Native context review identity differs")
        reviewed = json.loads(reviewed_path.read_text())
        if any(context.get(key) != reviewed.get(key) for key in ("law_context", "crossing")):
            raise ValueError("Native context differs from retained review")
        map_hash = hashlib.sha256(map_path.read_text().encode()).hexdigest()
        if reviewed["law_context"]["map_source"] != map_hash:
            raise ValueError("Native map differs from retained review")
    elif provenance.get("provenance_kind") != "synthetic_fixture":
        raise ValueError("Unknown acquisition provenance kind")
    ego = _rows(sources["ego-body-history.jsonl"])
    other = _rows(sources["other-body-history.jsonl"])
    if len(ego) != len(other):
        raise ValueError("Ego and other original history lengths differ")
    for ego_row, other_row in zip(ego, other):
        if (ego_row.get("frame"), ego_row.get("time_s")) != (
                other_row.get("frame"), other_row.get("time_s")):
            raise ValueError("Ego and other original frame/time join differs")
        if ego_row.get("actor_id") != context.get("ego_actor_id") or (
                other_row.get("actor_id") != context.get("other_actor_id")):
            raise ValueError("Original actor identity differs from crossing context")
    trace = {
        "context": context["law_context"],
        "crossing": context["crossing"],
        "ego_samples": [{"frame": row["frame"], "body_vertices_xy_m": row["body_vertices_xy_m"]}
                        for row in ego],
        "other_samples": [{"frame": row["frame"], "body_vertices_xy_m": row["body_vertices_xy_m"]}
                          for row in other],
    }
    observed = crossing_entry_measurement(trace)
    observed.update(ego_actor_id=context["ego_actor_id"],
                    other_actor_id=context["other_actor_id"],
                    first_time_s=ego[0]["time_s"], last_time_s=ego[-1]["time_s"])
    return {
        "format": "worker-analysis-report",
        "measurements": {"crossing_entry_measurement": {
            "value": observed,
            "method": "crossing_entry_measurement",
            "sources": {name: acquisition[name]["sha256"] for name in SOURCES},
        }},
        "limitations": ["Highway/public-access and device source labels require independent provenance review.",
                        "Subsection 4 qualification and legal right-of-way remain unresolved."],
        "analysis_complete": True,
        "legal_verdict_claimed": False,
    }


def saved_result(attempt, report):
    """Build a Native result and converter channels from unmodified acquisition."""
    from worker_exchange.native_output import physical_result, validate_result

    attempt = Path(attempt)
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    description = construction["recording_description"]
    acquisition = json.loads((attempt / "acquisition.json").read_text())
    sources = {name: _source(attempt, acquisition, name) for name in SOURCES}
    context = json.loads(sources["intersection-context.json"].read_text())
    bounds = context["crossing"]["bounds_xy_m"]
    expected_polygon = [[bounds[0], bounds[1]], [bounds[2], bounds[1]],
                        [bounds[2], bounds[3]], [bounds[0], bounds[3]]]
    if config["physical_completion"]["intersection_polygon_xy_m"] != expected_polygon:
        raise ValueError("physical completion polygon differs from original crossing context")
    if (config["law_id"], config["cell_id"], config["actor"]) != (
            "NRS-484B-250-1", "C125714", "motor_vehicle_driver"):
        raise ValueError("saved finalizer assignment identity differs")
    if type(config["case"]["other_entered_first"]) is not bool:
        raise ValueError("entry-order target must be a boolean")
    ego = _rows(sources["ego-body-history.jsonl"])
    other = _rows(sources["other-body-history.jsonl"])
    channel_values = {
        "ego_body_history": [(r["time_s"], r["body_vertices_xy_m"]) for r in ego],
        "other_body_history": [(r["time_s"], r["body_vertices_xy_m"]) for r in other],
    }
    context_values = {
        "crossing_geometry": context["crossing"],
        "highway_identity": {key: context["law_context"][key] for key in
                             ("ego_highway", "other_highway", "public_access")},
        "device_inventory": context["law_context"]["devices"],
        "driver_scope": {"human_driver": context["law_context"]["human_driver"]},
    }
    output = attempt / "channels"
    output.mkdir(exist_ok=True)
    evidence = []
    for item in description["channels"]:
        name = item["name"]
        if name not in channel_values:
            raise ValueError("Unsupported declared channel: " + name)
        path = output / (name + ".jsonl")
        with path.open("x") as stream:
            for time_s, value in channel_values[name]:
                stream.write(json.dumps({"time_s": time_s, "value": value}, allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": item["unit"],
                         "reference": str(path.relative_to(attempt))})
    context_path = output / "context.json"
    context_path.write_text(json.dumps(context_values, allow_nan=False) + "\n")
    for item in description["context_inputs"]:
        if item["name"] not in context_values:
            raise ValueError("Unsupported declared context: " + item["name"])
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context_path.relative_to(attempt))})
    observed = report["measurements"]["crossing_entry_measurement"]["value"]
    requested = config["case"]["other_entered_first"]
    matched = observed["other_entered_before_ego"] == requested
    result = {
        "case_id": config["selected_case_id"],
        "measured_values": observed,
        "target_checks": [{"target": "original crossing entry order",
                           "requested": requested,
                           "measured": observed["other_entered_before_ego"],
                           "method": "joined original body-polygon entry frames",
                           "tolerance": 0, "matched": matched,
                           "physical_cause_confirmed": False,
                           "cause_evidence": report["measurements"]["crossing_entry_measurement"]["sources"]}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "Saved evidence assessment pending physical review",
        "physical_failure_flags": [], "trace_reference": "trace.jsonl",
        "video_references": ["overview.mkv", "approach.mkv",
                             "reference_corner.mkv", "driver_reference.mkv"],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description, "recording_evidence": evidence,
        "realized_observables": {},
    }
    result = physical_result(attempt, result)
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = build_report(args.attempt)
    result = saved_result(args.attempt, report)
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    with (Path(args.attempt) / "result.json").open("x") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
