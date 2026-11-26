"""Bind exact diagnostic recipes and finalizer contract to the draft manifest."""

import hashlib
import json
from pathlib import Path

from school_warning_scene import CASE_VARIANTS


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def bind(manifest_name="draft-native-manifest.json"):
    manifest_path = ROOT / manifest_name
    manifest = json.loads(manifest_path.read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    dispositions = plan["requirement_dispositions"]
    manifest["runtime_manifest_sha256"] = sha(REPO / "runtime/SOURCE-MANIFEST.json")
    proposals = []
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[1]
        construction = json.loads((ROOT / entry["construction"]).read_text())
        description = construction["recording_description"]
        contract_path = ROOT / "diagnostic" / suffix / "measurement-contract.json"
        keys = ("school_warning_stop", "warning_actor_role", "observed_release")
        types = ("object", "text", "text")
        requirements = []
        for index, disposition in enumerate(dispositions):
            if disposition["status"] != "selected_required" or entry["case_id"] not in disposition.get("case_ids", []):
                continue
            requirements.append({"disposition_index": index,
                "requirement": disposition["requirement"],
                "source": disposition["source"],
                "output_key": keys[index], "method": "derive",
                "kind": "measured", "value_type": types[index],
                "inputs": ["road.xodr", "native-rows.jsonl", "video_frames.jsonl",
                           "original-school-lane-review.json"]})
        contract = {"format": "worker-measurement-contract",
            "case_id": entry["case_id"], "requirements": requirements,
            "negative": {"remove": ["original-school-lane-review.json"],
                         "error_contains": "Missing required source: original-school-lane-review.json"}}
        write(contract_path, contract)
        entry["measurement_contract"] = str(contract_path.relative_to(ROOT))
        entry["measurement_procedure"] = {"entrypoint": "finalize.py"}
        entry["fixture_recipe"] = str((ROOT / "diagnostic" / suffix /
                                       "fixture-recipe.json").relative_to(REPO))
        proposals.append({"case_id": entry["case_id"],
            "target_law_id": "LVMC-11-46-030", "target_type": "controlled_stop_request",
            "cell_id": "C394563", "actor": "motor_vehicle_driver",
            "rationale": "Sourced " + CASE_VARIANTS[suffix][1] +
                         " school warning with requested centre stop " +
                         str(CASE_VARIANTS[suffix][0]) +
                         " feet from nearest side and " + CASE_VARIANTS[suffix][2] +
                         " release; actual physical/legal result unverified",
            "variable_assignments": {
                "requested_stop_center_ft": {"kind": "controller",
                    "value": CASE_VARIANTS[suffix][0], "unit": "feet"},
                "requested_release_event": {"kind": "environment",
                    "value": CASE_VARIANTS[suffix][2]},
                "warning_role": {"kind": "environment",
                    "value": CASE_VARIANTS[suffix][1]},
                "observed_stop_position": {"kind": "subject_behavior",
                    "value": None, "unit": "feet"}},
            "unresolved_judgment_calls": ["school pedestrian lane identity",
                "warning of children about to cross or crossing",
                "statutory vehicle reference point", "observed release meaning"],
            "recording_description": description,
            "paired_probe_id": "school_warning_stop_distance",
            "deliberate_differences": ["requested_stop_center_ft"]})
    proposal = {"cell_id": "C394563", "actor": "motor_vehicle_driver",
                "status": "draft", "sweep_specs": [], "sweeps_expanded": True,
                "cases": proposals}
    proposal_name = "variant-cases.json" if manifest_name == "draft-variant-manifest.json" else "cases.json"
    write(ROOT / "proposals" / proposal_name, proposal)
    write(manifest_path, manifest)
    return {"cases": len(proposals), "manifest_sha256": sha(manifest_path)}


if __name__ == "__main__":
    import sys
    print(json.dumps(bind(sys.argv[1] if len(sys.argv) > 1 else "draft-native-manifest.json")))
