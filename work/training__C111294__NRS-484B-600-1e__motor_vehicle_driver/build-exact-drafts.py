"""Materialize twelve exact unselected C111294 construction bundles."""
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
         "measure_speed.py", "finalize.py")
TESTS = ("test_geometry_speed.py", "test_runner.py")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def recording_description() -> dict:
    units = {"ego_pose": "Native x,y,z metres", "ego_speed": "metres/second",
             "observed_speed": "miles/hour", "other_vehicle_pose": "Native x,y,z metres"}
    return {"channels": [{"name": name, "unit": unit, "sampling_rate_hz": 20,
              "method": "original frame-joined Native actor readback",
              "time_window": "entire 24 s / 480 frame attempt",
              "reference_frame": "surveyed Native map and original frame identity",
              "uncertainty": "50 ms samples; velocity/pose consistency and 0.2 mph saved interval"}
              for name, unit in units.items()],
            "context_inputs": [{"name": "other_vehicle", "unit": "structured",
                                "method": "separate actor route, velocity, full body and frame identity"}],
            "limitations": ["Requested speed and controller response require original Native readback",
                            "Synthetic CPU measurement is not physical speed or a legal verdict"]}


def build() -> dict:
    plan = json.loads((HERE / "case-plan.json").read_text())
    batch = json.loads((ROOT / "batch.json").read_text())
    common = [{"path": name, "content": (NATIVE / name).read_text()} for name in FILES]
    common.extend({"path": "tests/" + name, "content": (NATIVE / name).read_text()}
                  for name in TESTS)
    recording = recording_description()
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": HERE.name,
                "runtime_manifest_sha256": batch["runtime"]["source_manifest_sha256"],
                "status": "draft_not_selected", "cases": []}
    for case in plan["cases"]:
        suffix = case["case_id"].split("__")[-1]
        contract = f"draft-measurement-contract-{suffix}.json"
        if json.loads((HERE / contract).read_text())["case_id"] != case["case_id"]:
            raise ValueError("Case measurement contract differs")
        entry = {"case_id": case["case_id"], "kind": "draft_not_selected",
                 "measurement_contract": contract,
                 "candidate_risk": {"status": "physical",
                    "reason": "Native map/actor readback, speed attainment, camera pixels and physical traffic unobserved"},
                 "measurement_procedure": {"entrypoint": "finalize.py",
                    "output_schema": "c111294-saved-speed-measurement-v1"},
                 "candidates": []}
        recipe_path = HERE / f"update015-{suffix}-recipe.json"
        if recipe_path.is_file():
            entry["fixture_recipe"] = str(recipe_path.relative_to(ROOT))
        for candidate in CANDIDATES:
            policy = candidate_plan(suffix, candidate)
            config = {"case_id": case["case_id"],
                      "selected_case_id": case["case_id"],
                      "supported_case_ids": [case["case_id"]],
                      "case_suffix": suffix, "candidate_id": candidate,
                      "cell_id": "C111294", "law_id": "NRS-484B-600-1e",
                      "actor": "motor_vehicle_driver", "rate_hz": 20,
                      "duration_s": 24, "requested_setting_mph": case["requested_setting"],
                      "comparison_variable": "observed_speed",
                      "measurement_contract": "measurement-contract.json",
                      "required_atoms": ["kin.speed", "kin.velocity"],
                      "source_packets": [],
                      "frozen_source_hashes": plan["sources"],
                      "mandatory_channels": ["ego_pose", "ego_speed",
                                             "observed_speed", "other_vehicle_pose"],
                      "case": {"case_id": case["case_id"]},
                      "knobs": policy["knobs"],
                      "recording_description": recording,
                      "cameras": camera_plan(),
                      "status": "unselected_native_draft"}
            files = common + [{"path": "measurement-contract.json",
                               "content": (HERE / contract).read_text()},
                              {"path": "config.json",
                               "content": json.dumps(config, indent=2) + "\n"}]
            construction = {"case_id": case["case_id"],
                "law_id": "NRS-484B-600-1e", "cell_id": "C111294",
                "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
                "files": files, "recording_description": recording,
                "measurement_plan": {"method": "source-hashed saved 480-frame Native velocity, pose and separate actor route",
                                     "status": "synthetic_cpu_contract_proven_not_delivery_compatible"},
                "static_checks": ["long-road and two-direction junction CPU geometry",
                                  "reflected lane survey and four cameras",
                                  "source-bound 480-frame speed/pose/control tests"],
                "termination_rules": ["480 original 20 Hz frames",
                                      "retain failed capture/restoration report"],
                "mechanisms": ["same-cell long-road through route",
                               "separate opposing vehicle route",
                               "feedback speed/steering controller",
                               "four original FFV1 cameras"],
                "status": "unselected_cpu_draft"}
            relative = f"exact-drafts/{suffix}/{candidate}/construction.json"
            path = HERE / relative
            write(path, construction)
            ref = {"id": candidate, "construction": relative,
                   "construction_sha256": sha(path)}
            if candidate == "primary":
                entry.update(ref)
            else:
                trigger = policy["fallback_trigger"]
                ref.update({"trigger": {"source": trigger["source"],
                                        "metric": trigger["metric"],
                                        "failure_condition": f"{trigger['metric']} {trigger['op']} {trigger['threshold']}"},
                            "changed_knobs": list(policy["changed_knobs"])})
                entry["candidates"].append(ref)
        manifest["cases"].append(entry)
    write(HERE / "draft-execution-manifest.json", manifest)
    write(HERE / "proposals/cases.json", {"status": "unselected_cpu_drafts",
        "cases": [{"case_id": case["case_id"], "target_law_id": "NRS-484B-600-1e",
            "target_type": "boundary_probe", "cell_id": "C111294",
            "actor": "motor_vehicle_driver", "recording_description": recording,
            "sweep_measurements": [], "comparison_variable": "observed_speed",
            "requested_setting": case["requested_setting"],
            "status": "unselected_draft"} for case in plan["cases"]]})
    return {"cases": len(manifest["cases"]),
            "candidates": sum(1 + len(c["candidates"]) for c in manifest["cases"]),
            "selected": False}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
