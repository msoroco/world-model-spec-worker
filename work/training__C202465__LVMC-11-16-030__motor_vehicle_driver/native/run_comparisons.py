"""Audit all rail comparisons from source-bound saved CPU selections."""

import copy
import hashlib
import json
from pathlib import Path

from comparison_audit import audit

WORK = Path(__file__).resolve().parents[1]
PLAN = WORK / "case-plan.json"
MANIFEST = WORK / "execution-manifest.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_case(entry):
    proof = entry["saved_proof"]
    processing = json.loads(Path(proof["processing"]).read_text())
    stage = Path(processing["analysis_directory"])
    config = json.loads((stage / "config.json").read_text())
    railway = json.loads((stage / "original-source-review/railway.json").read_text())
    body_rows = [json.loads(line) for line in (stage / "rail-body.jsonl").read_text().splitlines()]
    ray_rows = [json.loads(line) for line in (stage / "rail-rays.jsonl").read_text().splitlines()]
    rows = [json.loads(line)["value"] for line in
            (stage / "channels/st.sight_distance.jsonl").read_text().splitlines()]
    if (len(rows) != 600 or len(body_rows) != 600 or len(ray_rows) != 600
            or any(row["native_frame"] != body["frame"] or row["native_frame"] != ray["frame"]
                   for row, body, ray in zip(rows, body_rows, ray_rows))):
        raise ValueError("Original body/ray/analysis frame join differs")
    crossing = {
        "grade_crossing_source": railway["source_sha256"],
        "railway_source": railway["source_sha256"],
        "approach_route_source": sha(stage / "original-source-review/approach.source.txt"),
    }
    metadata = {
        "road_sha256": sha(stage / "road.xodr"),
        "railway_review_sha256": sha(stage / "original-source-review/railway.json"),
        "approach_review_sha256": sha(stage / "original-source-review/approach.json"),
        "camera_plan_sha256": hashlib.sha256(json.dumps(config["cameras"], sort_keys=True).encode()).hexdigest(),
        "ego_blueprint": config["ego_blueprint_filter"],
        "rail_vehicle_actor_ids": railway["rail_vehicle_actor_ids"],
        "crossing_source_ref": railway["source_sha256"],
        "flagman_source_ref": sha(stage / "original-source-review/flagman.source.txt"),
        "signal_source_ref": sha(stage / "original-source-review/signal.source.txt"),
        "blocker_source_refs": config["sight_mode"],
        "diagnostic_fixture": True,
    }
    return {"case_id": entry["case_id"], "source_metadata": metadata,
            "crossing": crossing, "rows": rows,
            "source_hashes": {name: sha(stage / name) for name in
                              ("rail-body.jsonl", "rail-rays.jsonl", "reviewed-exceptions.jsonl",
                               "video_frames.jsonl", "trace.jsonl")},
            "saved_processing_sha256": sha(proof["processing"])}


def main():
    plan = json.loads(PLAN.read_text())
    manifest = json.loads(MANIFEST.read_text())
    selections = {entry["case_id"]: source_case(entry) for entry in manifest["cases"]}
    axes = {"speed_15_mph": "speed", "speed_at_15_mph": "speed",
            "left_sight": "sight", "right_sight": "sight", "crossing_view": "sight",
            "flagman_exception": "flagman", "inactive_signal_exception": "signal_state",
            "signal_indication": "signal_state", "signal_visibility": "signal_visibility"}
    receipts = []
    for comparison in plan["comparisons"]:
        suffix = comparison["comparison_id"].split("__")[-1]
        members = [selections[case_id] for case_id in comparison["case_ids"]]
        declaration = {"comparison_id": comparison["comparison_id"],
                       "case_ids": comparison["case_ids"], "axis": axes[suffix]}
        positive = audit(*members, declaration, diagnostic_fixture=True)
        incorrect = copy.deepcopy(members[1])
        incorrect["source_metadata"]["road_sha256"] = "0" * 64
        try:
            audit(members[0], incorrect, declaration, diagnostic_fixture=True)
        except ValueError as error:
            if "fixed original source differs: road_sha256" not in str(error):
                raise
        else:
            raise ValueError("Comparison accepted mismatched original source")
        output = dict(positive, source_cases=[{key: value for key, value in item.items()
                                              if key in ("case_id", "source_hashes", "saved_processing_sha256")}
                                             for item in members],
                      negative_expected_error="fixed original source differs: road_sha256",
                      negative_rejected=True)
        path = WORK / "comparison-proofs" / (suffix + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(output, indent=2) + "\n")
        receipts.append({"comparison_id": comparison["comparison_id"],
                         "case_ids": comparison["case_ids"], "receipt": str(path.relative_to(WORK)),
                         "sha256": sha(path), "diagnostic_only": True})
        print("PASS comparison", suffix, flush=True)
    (WORK / "comparison-audit-specs.json").write_text(json.dumps({"comparisons": receipts}, indent=2) + "\n")


if __name__ == "__main__":
    main()
