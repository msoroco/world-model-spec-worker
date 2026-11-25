"""Bind the two exact roundabout source constructions for public CPU proofs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
ASSIGNMENT = FOLDER.name
RUNTIME_SHA = "5e2dd81ac49dd2d9814a10b71ee30cf85323868a8369116020b06a69cbfcc5e3"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    plan = json.loads((FOLDER / "case-plan.json").read_text())
    for disposition in plan["requirement_dispositions"]:
        if disposition["requirement"] == "reviewed-scope-0":
            disposition["status"] = "selected_required"
            disposition["case_ids"] = [case["case_id"] for case in plan["cases"]]
            disposition["evidence_or_gap"] = (
                "Frozen accepted witness supports this selected comparison; original Native "
                "geometry, timing and legal sufficiency remain unverified.")
    for case in plan["cases"]:
        case["planning_status"] = "selected_cpu_preparation_in_progress"
    for comparison in plan["comparisons"]:
        comparison["status"] = "selected_cpu_preparation_in_progress"
        comparison["audit_gap"] = "Independent saved comparison and original Native outcomes pending."
    write(FOLDER / "case-plan.json", plan)
    draft = json.loads((HERE / "draft-manifest.json").read_text())
    entries = []
    proposals = []
    for condition in ("condition_a", "condition_b"):
        old = next(row for row in draft["cases"] if row["case_id"].endswith(condition))
        case_id = old["case_id"]
        construction = json.loads((HERE / old["construction"]).read_text())
        config = json.loads(next(file["content"] for file in construction["files"]
                                 if file["path"] == "config.json"))
        requirements = [
            {"disposition_index": 0, "requirement": "text-0",
             "source": "LVMC 11.43.010(B)", "output_key": "roundabout_context",
             "method": "measure_roundabout_context", "value_type": "object",
             "kind": "sourced_context", "inputs": ["roundabout-map-readback.json", "road.xodr"]},
            {"disposition_index": 1, "requirement": "text-1",
             "source": "LVMC 11.43.010(B)", "output_key": "yield_order",
             "method": "measure_yield_order", "value_type": "object",
             "kind": "measured", "inputs": ["native-raw-actors.jsonl",
                                            "control-intent.jsonl", "video_frames.jsonl"]},
            {"disposition_index": 2, "requirement": "reviewed-scope-0",
             "source": "inputs/planning/focused-coverage-20261016-v1/coverage-witnesses.json",
             "output_key": "gap_timing", "method": "measure_gap_timing",
             "value_type": "object", "kind": "measured",
             "inputs": ["native-raw-actors.jsonl", "video_frames.jsonl"]}]
        contract_rel = "selected-measurements/" + condition + "/measurement-contract.json"
        write(FOLDER / contract_rel, {"format": "worker-measurement-contract",
             "case_id": case_id, "requirements": requirements,
             "negative": {"remove": ["roundabout-map-readback.json"],
                          "error_contains": "Missing required source: roundabout-map-readback.json"}})
        proposals.append({"case_id": case_id, "target_law_id": "LVMC-11-43-010-B",
            "target_type": "controlled_comparison", "rationale": "Frozen roundabout-entry witness",
            "paired_probe_id": "c239014_entry_gap", "deliberate_differences": ["entry_release_time"],
            "probe": {"primary_variable": "entry_release_time",
                      "comparison_or_standard": "original source traffic brackets; legal sufficiency unresolved",
                      "target_value_or_branch": condition},
            "variable_assignments": {"entry_release_time": {
                "kind": "controller", "value": config["entry_release_s"]}},
            "recording_description": config["recording_description"],
            "unresolved_judgment_calls": ["full boundary, traffic gap sufficiency and driver duty"]})
        entries.append({"case_id": case_id, "kind": "delivery",
            "construction": "native/" + old["construction"],
            "construction_sha256": old["construction_sha256"],
            "candidate_risk": {"status": "none",
                "reason": "Primary map/controller realization needs original Native review before a fallback trigger can be chosen."},
            "candidates": [], "measurement_procedure": {"entrypoint": "finalize.py"},
            "measurement_contract": contract_rel,
            "fixture_recipe": str((FOLDER / ("diagnostic-" + condition + "-recipe.json")).relative_to(HERE.parents[2])),
            "delivery_readiness": "incomplete",
            "id": "primary"})
    write(FOLDER / "proposals/cases.json", {"cell_id": "C239014",
        "actor": "motor_vehicle_driver", "status": "draft", "cases": proposals,
        "sweep_specs": [], "sweeps_expanded": True})
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": RUNTIME_SHA,
                "status": "selected_delivery_cpu_in_progress", "cases": entries}
    write(FOLDER / "execution-manifest.json", manifest)
    return {"manifest_sha256": sha(FOLDER / "execution-manifest.json"),
            "cases": [{"case_id": row["case_id"],
                       "construction_sha256": row["construction_sha256"]}
                      for row in entries]}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
