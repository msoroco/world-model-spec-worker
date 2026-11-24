"""Source-bound intention, lane and connector observations for LVMC 11.43.010(C)(2)."""

import argparse
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT_ID = "testing__C240647__LVMC-11-43-010-C2__motor_vehicle_driver"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(case_id, context_path, trace_path, receipt_path):
    if not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise ValueError("exact assignment case required")
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    if (receipt.get("assignment_id"), receipt.get("case_id")) != (ASSIGNMENT_ID, case_id):
        raise ValueError("original source receipt identity mismatch")
    if receipt.get("diagnostic_fixture") or receipt.get("source_kind") != "original_native_capture":
        raise ValueError("original Native capture required")
    if receipt.get("context_sha256") != sha(context_path) or receipt.get("trace_sha256") != sha(trace_path):
        raise ValueError("original source bytes changed")
    context = json.loads(Path(context_path).read_text(encoding="utf-8"))
    if context.get("case_id") != case_id or not isinstance(context.get("map_sha256"), str) or len(context["map_sha256"]) != 64:
        raise ValueError("exact source map context required")
    for key in ("jurisdiction_source", "roundabout_graph_source", "right_lane_source",
                "right_exit_connector_source", "operator_identity_source", "operator_intent_source",
                "independent_route_source", "vehicle_class_source"):
        if not context.get(key):
            raise ValueError("original context source missing: " + key)
    lanes = context.get("circulating_lane_ids")
    if not isinstance(lanes, list) or not lanes or any(not isinstance(x, str) or not x for x in lanes) or len(set(lanes)) != len(lanes):
        raise ValueError("distinct original circulating lanes required")
    right_lane = context.get("right_lane_id")
    if right_lane not in lanes or not context.get("right_exit_connector_id"):
        raise ValueError("source right lane and connected exit required")
    if not context.get("operator_intended_exit_id") or context.get("operator_intended_exit_id") not in {context["right_exit_connector_id"],
                                                        context.get("through_exit_connector_id")}:
        raise ValueError("independent operator intent required")
    rows = [json.loads(line) for line in Path(trace_path).read_text(encoding="utf-8").splitlines() if line]
    if len(rows) < 2 or len(rows) != receipt.get("frame_count") or receipt.get("fps") != 20:
        raise ValueError("original 20 Hz frame count mismatch")
    observations = []
    for index, row in enumerate(rows):
        if row.get("frame") != index or not isinstance(row.get("time_s"), (int, float)) or abs(row["time_s"] - index / 20) > .002:
            raise ValueError("original frame cadence mismatch")
        section = row.get("section")
        if section not in {"approach", "circulating", "exit"}:
            raise ValueError("original roundabout section required")
        lane = row.get("lane_id")
        if section == "circulating" and lane not in lanes:
            raise ValueError("circulating lane missing from original graph")
        if section == "exit" and row.get("exit_connector_id") not in {
                context["right_exit_connector_id"], context.get("through_exit_connector_id")}:
            raise ValueError("exit connector missing from original graph")
        if section != "exit" and row.get("exit_connector_id") is not None:
            raise ValueError("premature exit connector")
        speed = row.get("speed_mps")
        if not isinstance(speed, (int, float)) or not math.isfinite(speed) or speed < 0:
            raise ValueError("original vehicle speed required")
        observations.append({"frame": index, "time_s": row["time_s"], "section": section,
                             "lane_id": lane, "exit_connector_id": row.get("exit_connector_id"),
                             "speed_mps": speed})
    circulating = [r for r in observations if r["section"] == "circulating"]
    if not circulating:
        raise ValueError("no observed roundabout operation")
    exit_rows = [r for r in observations if r["section"] == "exit"]
    if exit_rows and exit_rows[0]["frame"] <= circulating[0]["frame"]:
        raise ValueError("exit before roundabout operation")
    return {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
            "source_bindings": {"context_sha256": sha(context_path), "trace_sha256": sha(trace_path),
                                "receipt_sha256": sha(receipt_path), "native_map_sha256": context["map_sha256"]},
            "operator_intended_exit_id": context["operator_intended_exit_id"],
            "right_exit_connector_id": context["right_exit_connector_id"], "right_lane_id": right_lane,
            "first_observed_exit_connector_id": exit_rows[0]["exit_connector_id"] if exit_rows else None,
            "last_circulating_lane_id": circulating[-1]["lane_id"], "observations": observations,
            "right_turn_judgment": "unresolved", "right_lane_use_judgment": "unresolved",
            "physical_acceptance": "unverified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("case", "context", "trace", "receipt", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = measure(args.case, args.context, args.trace, args.receipt)
    Path(args.output).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
