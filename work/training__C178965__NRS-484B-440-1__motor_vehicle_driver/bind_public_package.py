"""Bind partial exact roadside cases to the public diagnostic runtime."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    source = plan["requirement_dispositions"][0]
    proposals = {"cell_id": "C178965", "actor": "motor_vehicle_driver", "status": "draft",
                 "sweep_specs": [], "sweeps_expanded": True, "cases": []}
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
                "status": "partial_cpu_preparation", "cases": []}
    for number in (1, 2, 3):
        tag = f"probe_0{number}"
        config = json.loads((HERE / "native/cases" / f"{tag}.json").read_text())
        case_id = config["case_id"]
        construction = f"native/cases/{tag}-construction.json"
        contract_path = HERE / "selected-measurements" / tag / "measurement-contract.json"
        write(contract_path, {"format": "worker-measurement-contract", "case_id": case_id,
            "requirements": [{"disposition_index": 0, "requirement": source["requirement"],
                "source": source["source"], "output_key": "roadside",
                "method": "measure_roadside", "value_type": "object", "kind": "measured",
                "inputs": ["roadside-native.jsonl", "visibility-native.jsonl",
                           "original-highway-survey.json", "video_frames.jsonl"]}],
            "negative": {"remove": ["visibility-native.jsonl"],
                         "error_contains": "Missing required source: visibility-native.jsonl"}})
        proposals["cases"].append({"case_id": case_id,
            "target_law_id": "NRS-484B-440-1", "target_type": "judgment_sweep",
            "rationale": "Exact surveyed roadside stop, width, 200-foot view and disabled branch",
            "paired_probe_id": "c178965_roadside_position_and_failure",
            "deliberate_differences": plan["comparisons"][0]["deliberate_differences"],
            "probe": {"primary_variable": "stop_mode",
                      "comparison_or_standard": "off-pavement position versus on-pavement position and disabled exception",
                      "target_value_or_branch": config["stop_mode"]},
            "variable_assignments": {"stop_mode": {"kind": "controller", "value": config["stop_mode"]}},
            "recording_description": config["recording_description"],
            "unresolved_judgment_calls": ["off-part practicability", "free passage",
                                          "driver recognizability at 200 feet", "disabled impossibility"]})
        manifest["cases"].append({"case_id": case_id, "kind": "delivery",
            "construction": construction, "construction_sha256": sha(HERE / construction),
            "candidate_risk": {"status": "physical",
                               "reason": "Native steering or braking may miss the surveyed roadside target."},
            "candidates": [], "measurement_procedure": {"entrypoint": "finalize.py"},
            "measurement_contract": str(contract_path.relative_to(HERE)),
            "fixture_recipe": f"work/{ASSIGNMENT}/diagnostic-{tag}-recipe.json",
            "native_handoff": {"python_env_var": "CARLA_PYTHON",
                               "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}})
    write(HERE / "proposals/cases.json", proposals)
    write(HERE / "execution-manifest.json", manifest)
    print(json.dumps({"manifest_sha256": sha(HERE / "execution-manifest.json"),
                      "cases": [case["case_id"] for case in manifest["cases"]]}))


if __name__ == "__main__":
    main()
