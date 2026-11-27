"""Expose the selected shoulder construction and source observation plan."""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NATIVE = ROOT / "native"


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    primary = json.loads((NATIVE / "selected-witness_1-construction.json").read_text())
    config = json.loads(next(item["content"] for item in primary["files"]
                             if item["path"] == "config.json"))
    plan_path = ROOT / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    config["supported_case_ids"] = [item["case_id"] for item in plan["cases"]]
    for camera in config["cameras"]:
        camera["pose_strategy"] = "vehicle_attached_fixed_source_view"
    shutil.copyfile(NATIVE / "selected_runner.py", ROOT / "runner.py")
    write(ROOT / "config.json", config)
    (ROOT / "tests").mkdir(exist_ok=True)
    shutil.copyfile(NATIVE / "selected_offline_test.py", ROOT / "tests/test_offline.py")
    construction = json.loads(json.dumps(primary))
    construction["files"] = []
    for name, path in (("runner.py", ROOT / "runner.py"),
                       ("config.json", ROOT / "config.json"),
                       ("tests/test_offline.py", ROOT / "tests/test_offline.py"),
                       ("finalize.py", NATIVE / "finalize.py"),
                       ("saved_shoulder.py", NATIVE / "saved_shoulder.py"),
                       ("shoulder_lamp_measure.py", NATIVE / "shoulder_lamp_measure.py")):
        item = {"path": name, "content": path.read_text()}
        if path.parent == NATIVE:
            item["source"] = "work/" + ROOT.name + "/native/" + path.name
        construction["files"].append(item)
    construction["measurement_plan"] = {
        "channels": [item["name"] for item in primary["recording_description"]["channels"]],
        "source": "original Native shoulder and lighting survey, lamp trace, four camera frames",
    }
    construction["static_checks"] = ["exact law and cell identity", "mapped shoulder",
                                     "four source cameras", "20 Hz for 30 seconds",
                                     "original lighting, lamp and optical sources"]
    construction["termination_rules"] = ["600 original simulation frames",
                                          "encoder closure", "world restoration",
                                          "Native exit before saved analysis"]
    construction["mechanisms"] = ["surveyed shoulder and passing traffic side",
                                   "full stopped-vehicle lamp command trace",
                                   "source-bound optical and installation review"]
    write(ROOT / "construction.json", construction)
    plan["camera_plan"] = {
        "profile": "overview1080-capability", "duration_s": 30,
        "composition": "synchronized_four_view_primary",
        "coverage": [{"subject": subject, "interval": "all 30 seconds / 600 frames", "view": view}
                     for view, subject in (("overview", "stopped vehicle and shoulder"),
                                           ("approach", "traffic approach and ambient reveal"),
                                           ("reference_corner", "front/rear and near-side lamps"),
                                           ("driver_reference", "driver and lighting context"))],
    }
    refs = ["native/selected-witness_1-fixture-recipe.json",
            "native/selected-witness_2-fixture-recipe.json", "native/saved_shoulder.py"]
    plan["source_observation_mapping"] = {
        item["name"]: {"evidence": "original source-joined stopped interval and four-camera review; no legal verdict",
                       "channels": [item["name"]], "source_refs": refs}
        for item in plan["observations"]}
    for item in plan["observations"]:
        item["status"] = "cpu_source_bound_original_native_pending"
    for item in plan["cases"]:
        item["planning_status"] = "cpu_prepared_original_native_pending"
    for item in plan["comparisons"]:
        item["status"] = "cpu_prepared_original_native_pending"
        item["audit_gap"] = "Original Native optical pixels, lamp installation, physical completion and legal review remain pending."
    write(plan_path, plan)
    print(json.dumps({"root_case": primary["case_id"], "selected_cases": len(plan["cases"])}))


if __name__ == "__main__":
    main()
