"""Bind exact diagnostic recipes and finalizer contract to the draft manifest."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def bind():
    manifest_path = ROOT / "draft-native-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    disposition = plan["requirement_dispositions"][0]
    manifest["runtime_manifest_sha256"] = sha(REPO / "runtime/SOURCE-MANIFEST.json")
    proposals = []
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[1]
        construction = json.loads((ROOT / entry["construction"]).read_text())
        description = construction["recording_description"]
        contract_path = ROOT / "diagnostic" / suffix / "measurement-contract.json"
        contract = {"format": "worker-measurement-contract",
            "case_id": entry["case_id"],
            "requirements": [{"disposition_index": 0,
                "requirement": disposition["requirement"],
                "source": disposition["source"],
                "output_key": "school_warning_stop", "method": "derive",
                "kind": "measured", "value_type": "object",
                "inputs": ["road.xodr", "native-rows.jsonl", "video_frames.jsonl",
                           "original-school-lane-review.json"]}],
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
            "rationale": "Sourced school warning with requested centre stop " +
                         ("55" if suffix == "probe_1" else "40") +
                         " feet from nearest side; actual physical/legal result unverified",
            "variable_assignments": {
                "requested_stop_center_ft": {"kind": "controller",
                    "value": 55 if suffix == "probe_1" else 40, "unit": "feet"},
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
    write(ROOT / "proposals/cases.json", proposal)
    write(manifest_path, manifest)
    return {"cases": len(proposals), "manifest_sha256": sha(manifest_path)}


if __name__ == "__main__":
    print(json.dumps(bind()))
