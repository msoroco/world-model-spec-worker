"""Independent saved-output audit for C147331 controlled comparisons."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shlex

from lane_comparison_audit import audit_comparison


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
             "marking_inventory_sha256": canonical_hash(markings),
             "ego_blueprint": config.get("ego_blueprint", "vehicle.tesla.model3"),
             "camera_plan_sha256": canonical_hash(config["cameras"]),
             "duration_s": config["duration_s"], "fps": config["rate_hz"],
             "passing_participant_id": measurement["value"]["overtaken_id"]}
    return {"case_id": case_id, "source_sha256": digest(source),
            "measurement_sha256": digest(report_path), "fixed": fixed,
            "frames": frames,
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proofs", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = audit_proofs(args.proofs)
    output = Path(args.output)
    if output.exists():
        raise ValueError("Retain prior comparison audit")
    output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
