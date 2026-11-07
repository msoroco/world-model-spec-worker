"""Build exact unselected Native bundles for two controlled approach cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE = HERE / "native"
sys.path.insert(0, str(NATIVE))
from cameras import camera_plan
from engineering import CANDIDATES, candidate_plan

FILES = ("runner.py", "geometry.py", "engineering.py", "cameras.py",
         "measure_approach.py", "finalize.py", "authored-road.xodr", "draft-candidates.json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def build() -> dict:
    plan = json.loads((HERE / "case-plan.json").read_text())
    batch = json.loads((ROOT / "batch.json").read_text())
    common = [{"path": name, "content": (NATIVE / name).read_text()} for name in FILES]
    common.append({"path": "tests/test_runner.py", "content": (NATIVE / "test_runner.py").read_text()})
    for name in ("decrease", "hold"):
        path = HERE / "draft-fixtures" / f"{name}-synthetic-native.jsonl"
        common.append({"path": f"draft-fixtures/{name}-synthetic-native.jsonl",
                       "content": path.read_text()})
    recording = {"channels": [{"name": name, "unit": unit,
                "sampling_rate_hz": 20, "method": "original Native frame-joined actor readback",
                "time_window": "480 frames at 20 Hz", "reference_frame": "surveyed Native map",
                "uncertainty": "50 ms sampling and pose/velocity consistency"}
                for name, unit in (("ego_pose", "metres"), ("ego_speed", "metres/second"),
                    ("observed_speed", "miles/hour"), ("other_vehicle_pose", "metres"))],
                "context_inputs": [{"name": "intersection_and_other_vehicle", "unit": "structured",
                    "method": "authored OpenDRIVE and original cross-traffic actor readback"}],
                "limitations": ["Necessity of reduction and legal outcome require physical review",
                    "Synthetic CPU traces are diagnostic only"]}
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": HERE.name,
                "runtime_manifest_sha256": batch["runtime"]["source_manifest_sha256"],
                "status": "draft_not_selected", "cases": []}
    for case in plan["cases"]:
        suffix = case["case_id"].split("__")[-1]
        contract_path = HERE / f"draft-measurement-contract-{suffix}.json"
        contract = json.loads(contract_path.read_text())
        if contract["case_id"] != case["case_id"]:
            raise ValueError("Case measurement contract differs")
        row = {"case_id": case["case_id"], "kind": "draft_not_selected",
               "measurement_contract": contract_path.name,
               "candidate_risk": {"status": "physical", "reason":
                 "CARLA lane readback, original actor tracking, pixels and due-care necessity unobserved"},
               "measurement_procedure": {"entrypoint": "finalize.py",
                 "output_schema": "c111294-saved-approach-diagnostic-v1"},
               "candidates": []}
        for candidate in CANDIDATES:
            policy = candidate_plan(suffix, candidate)
            config = {"case_id": case["case_id"], "selected_case_id": case["case_id"],
                      "supported_case_ids": [case["case_id"]], "case_suffix": suffix,
                      "candidate_id": candidate, "cell_id": "C111294",
                      "law_id": "NRS-484B-603-1", "actor": "motor_vehicle_driver",
                      "rate_hz": 20, "duration_s": 24,
                      "comparison_variable": "hazard_approach_speed_profile",
                      "measurement_contract": "measurement-contract.json",
                      "required_atoms": ["kin.speed", "kin.velocity"],
                      "source_packets": [], "frozen_source_hashes": plan["sources"],
                      "mandatory_channels": ["ego_pose", "ego_speed", "observed_speed",
                                             "other_vehicle_pose"],
                      "case": {"case_id": case["case_id"]},
                      "knobs": policy["knobs"], "recording_description": recording,
                      "cameras": camera_plan(), "status": "unselected_native_draft"}
            files = common + [{"path": "measurement-contract.json", "content": contract_path.read_text()},
                              {"path": "config.json", "content": json.dumps(config, indent=2)+"\n"}]
            construction = {"case_id": case["case_id"], "law_id": "NRS-484B-603-1",
                "cell_id": "C111294", "actor": "motor_vehicle_driver",
                "entrypoint": "runner.py", "files": files,
                "recording_description": recording,
                "measurement_plan": {"method": "source-hashed 480-frame Native approach, pre-entry and crossing velocity/pose windows",
                                     "status": "synthetic_cpu_diagnostic_not_delivery_compatible"},
                "static_checks": ["six-road same-cell junction and lane preflight",
                                  "reflected Native approach target and cross-traffic survey",
                                  "source-hashed fallback and four original camera plans"],
                "termination_rules": ["480 original 20 Hz frames",
                                      "retain capture/restoration failure report"],
                "mechanisms": ["same-cell through intersection road",
                               "separate cross-traffic vehicle route",
                               "observed-y braking/hold feedback controller",
                               "four original FFV1 cameras"],
                "status": "unselected_cpu_draft"}
            relative = f"exact-drafts/{suffix}/{candidate}/construction.json"
            path = HERE / relative
            write(path, construction)
            ref = {"id": candidate, "construction": relative,
                   "construction_sha256": sha(path)}
            if candidate == "primary":
                row.update(ref)
            else:
                ref.update({"trigger": {"source": "hashed saved Native samples",
                    "metric": policy["fallback_triggers"][candidate]["metric"],
                    "failure_condition": policy["fallback_triggers"][candidate]["failure_condition"]},
                    "changed_knobs": [key for key, value in policy["knobs"].items()
                                      if candidate_plan(suffix, "primary")["knobs"].get(key) != value]})
                row["candidates"].append(ref)
        manifest["cases"].append(row)
    write(HERE / "draft-execution-manifest.json", manifest)
    write(HERE / "proposals/cases.json", {"status": "unselected_cpu_drafts",
        "cases": [{"case_id": case["case_id"], "target_law_id": "NRS-484B-603-1",
                   "target_type": case["target_type"], "cell_id": "C111294",
                   "actor": "motor_vehicle_driver", "recording_description": recording,
                   "comparison_variable": "hazard_approach_speed_profile",
                   "status": "unselected_draft"} for case in plan["cases"]]})
    return {"cases": len(manifest["cases"]), "candidates": 8, "selected": False}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
