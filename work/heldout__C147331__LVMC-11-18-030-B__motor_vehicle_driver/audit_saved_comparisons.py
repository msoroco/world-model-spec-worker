"""Independent saved-output audit for C147331 controlled comparisons."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shlex

from lane_comparison_audit import audit_comparison
from lane_finalizer import observed_lateral_fraction


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def canonical_hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def version_from_proof(row):
    words = shlex.split(row["command"])
    output = Path(words[words.index("--output") + 1])
    version = output / "v0001"
    if digest(version / "processing.json") != row["receipt_sha256"]:
        raise ValueError("Saved processing receipt changed")
    return version


def load_packet(version, case_id):
    version = Path(version)
    receipt = json.loads((version / "processing.json").read_text())
    if (receipt.get("case_id") != case_id or receipt.get("missing_evidence") is not False
            or receipt.get("originals_preserved") is not True):
        raise ValueError("Saved lane processing incomplete or wrong case")
    stage = version / "analysis"
    report_path = stage / "analysis-report.json"
    report = json.loads(report_path.read_text())
    config = json.loads((stage / "config.json").read_text())
    result_path = stage / "result.json"
    if (report.get("case_id") != case_id or config.get("selected_case_id") != case_id
            or digest(result_path) != receipt.get("result_sha256")):
        raise ValueError("Saved lane analysis identity or result hash differs")
    measurement = report["measurements"]["lane_boundary_observation"]
    source = stage / "marked_lane_sources.jsonl"
    if measurement["sources"].get("marked_lane_sources.jsonl") != digest(source):
        raise ValueError("Saved lane measurement source hash differs")
    rows = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    frames = measurement["value"]["frames"]
    if len(rows) != len(frames) or any(row["frame"] != frame["frame"] for row, frame in zip(rows, frames)):
        raise ValueError("Saved lane source/frame count differs")
    geometry = [{"road_id": row["lane"]["road_id"],
                 "lane_id": row["lane"]["lane_id"],
                 "polygon": row["lane"]["polygon_xy_m"],
                 "heading": row["lane"]["lane_heading_xy"]} for row in rows]
    markings = [[row["lane"]["left_marking"], row["lane"]["right_marking"]]
                for row in rows]
    capture = json.loads((stage / "capture/manifest.json").read_text())
    fixed = {"map_id": capture["map"],
             "lane_geometry_sha256": canonical_hash(geometry),
             "initial_lane_geometry_sha256": canonical_hash(geometry[0]),
             "marking_inventory_sha256": canonical_hash(markings),
             "ego_blueprint": config.get("ego_blueprint", "vehicle.tesla.model3"),
             "camera_plan_sha256": canonical_hash(config["cameras"]),
             "duration_s": config["duration_s"], "fps": config["rate_hz"],
             "passing_participant_id": measurement["value"]["overtaken_id"]}
    turn_context = report["measurements"].get("turn_preparation_control", {}).get("value")
    if case_id.endswith("__within_marked_lane"):
        # Recompute the negative control from originals. Older analyzers retained
        # an obsolete cross-cell planning reference, which is not source evidence.
        turn_context = {
            "requested_route": rows[0].get("route_intent"),
            "boundary_excursion_observed": any(
                frame.get("minimum_corner_clearance_m", 0) < 0
                or frame.get("full_footprint_inside") is False for frame in frames),
            "left_indicator_readback_observed": any(
                "LeftBlinker" in str(row.get("ego_light_state")) for row in rows),
            "lawful_turn_preparation_confirmed": False,
        }
    sweep_fraction = None
    requested_fraction = config.get("engineering", {}).get("crossing_fraction")
    if "__passing_excursion-" in case_id:
        channel = stage / "lane_crossing_fraction.jsonl"
        samples = [json.loads(line) for line in channel.read_text().splitlines()
                   if line.strip()]
        recomputed = [observed_lateral_fraction(row) for row in rows]
        if (len(samples) != len(rows) or any(
                sample["frame"] != row["frame"]
                or abs(sample["value"] - value) > 1e-9
                for sample, row, value in zip(samples, rows, recomputed))):
            raise ValueError("Passing sweep derived fraction differs from original lane rows")
        sweep_fraction = max(recomputed)
    return {"case_id": case_id, "source_sha256": digest(source),
            "measurement_sha256": digest(report_path), "fixed": fixed,
            "frames": frames,
            "turn_preparation": turn_context,
            "sweep_fraction": sweep_fraction,
            "requested_fraction": requested_fraction,
            "measured_order_reversal": measurement["value"]["measured_order_reversal"],
            "passing_motion_source_sha256": digest(source)
            if measurement["value"]["overtaken_id"] is not None else None}


def audit_proofs(proof_path):
    proof = json.loads(Path(proof_path).read_text())
    packets = {row["case_id"].rsplit("__", 1)[-1]:
               load_packet(version_from_proof(row), row["case_id"])
               for row in proof["cases"]}
    ordinary = audit_comparison("ordinary_lane_containment",
                                packets["within_marked_lane"],
                                packets["unexcused_boundary_crossing"])
    passing = audit_comparison("passing_exception_context",
                               packets["unexcused_boundary_crossing"],
                               packets["passing_boundary_crossing"])
    return {"format": "worker-lane-saved-comparison-audit", "passed": True,
            "scope": "synthetic saved-output software proof only",
            "comparisons": [ordinary, passing], "legal_acceptance_claimed": False,
            "physical_acceptance_claimed": False}


def audit_sweep(versions):
    packets = []
    for version in versions:
        case_id = json.loads((version / "processing.json").read_text())["case_id"]
        packets.append(load_packet(version, case_id))
    suffixes = [packet["case_id"].rsplit("__", 1)[-1] for packet in packets]
    if suffixes != [f"passing_excursion-{index:04d}" for index in range(3)]:
        raise ValueError("Passing sweep case order differs")
    fixed = ("map_id", "initial_lane_geometry_sha256", "marking_inventory_sha256",
             "ego_blueprint", "camera_plan_sha256", "duration_s", "fps")
    if any(packet["fixed"][key] != packets[0]["fixed"][key]
           for packet in packets[1:] for key in fixed):
        raise ValueError("Passing sweep changed fixed source context")
    for packet in packets:
        if (packet["fixed"]["passing_participant_id"] is None
                or not packet["passing_motion_source_sha256"]
                or not packet["measured_order_reversal"]
                or not any(frame["boundary_crossing"] for frame in packet["frames"])
                or packet["sweep_fraction"] is None
                or packet["requested_fraction"] is None
                or abs(packet["sweep_fraction"] - packet["requested_fraction"]) > 1e-9):
            raise ValueError("Passing sweep lacks source-measured excursion or passing context")
    fractions = [packet["requested_fraction"] for packet in packets]
    if sorted(fractions) != [0.4, 0.6, 0.8]:
        raise ValueError("Passing sweep does not cover the three distinct requests")
    return {"comparison_id": "passing_excursion_sweep",
            "checked_cases": [packet["case_id"] for packet in packets],
            "fixed_fields": list(fixed), "requested_fractions": fractions,
            "measured_fractions": [packet["sweep_fraction"] for packet in packets],
            "status": "software_evidence_complete", "legal_verdict": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proofs")
    parser.add_argument("--comparison")
    parser.add_argument("--left-version")
    parser.add_argument("--right-version")
    parser.add_argument("--third-version")
    parser.add_argument("--assignment")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.proofs and not any((args.comparison, args.left_version, args.right_version,
                               args.third_version)):
        result = audit_proofs(args.proofs)
    elif args.comparison and args.left_version and args.right_version and not args.proofs:
        left_version, right_version = Path(args.left_version), Path(args.right_version)
        if args.comparison == "passing_excursion_sweep" and args.third_version:
            checked = audit_sweep([left_version, right_version,
                                   Path(args.third_version)])
        elif args.third_version is None:
            left_id = json.loads((left_version / "processing.json").read_text())["case_id"]
            right_id = json.loads((right_version / "processing.json").read_text())["case_id"]
            checked = audit_comparison(args.comparison,
                                       load_packet(left_version, left_id),
                                       load_packet(right_version, right_id))
        else:
            parser.error("Third version is only valid for the passing sweep")
        result = {"format": "worker-lane-saved-comparison-audit", "passed": True,
                  "scope": "synthetic saved-output software proof only",
                  "comparisons": [checked], "legal_acceptance_claimed": False,
                  "physical_acceptance_claimed": False}
    else:
        parser.error("Supply either --proofs or one comparison and two saved versions")
    if args.assignment and any(
            not case.startswith(args.assignment + "__")
            for item in result["comparisons"] for case in item["checked_cases"]):
        raise ValueError("Compared case differs from selected queue assignment")
    output = Path(args.output)
    if output.exists():
        raise ValueError("Retain prior comparison audit")
    output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
