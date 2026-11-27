"""Build the root first-case compatibility surface and source observation plan."""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent.parent
NATIVE = ROOT / "native"


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    primary = json.loads((NATIVE / "selected-a-construction.json").read_text())
    config = json.loads(next(item["content"] for item in primary["files"]
                             if item["path"] == "config.json"))
    selected = [item["case_id"] for item in json.loads((ROOT / "case-plan.json").read_text())["cases"]]
    config["supported_case_ids"] = selected
    for camera in config["cameras"]:
        camera["pose_strategy"] = "vehicle_attached_fixed_source_view"
    shutil.copyfile(NATIVE / "selected_runner.py", ROOT / "runner.py")
    write(ROOT / "config.json", config)
    tests = ROOT / "tests"
    tests.mkdir(exist_ok=True)
    shutil.copyfile(NATIVE / "selected_offline_test.py", tests / "test_offline.py")
    construction = json.loads(json.dumps(primary))
    construction["files"] = []
    sources = {"runner.py": ROOT / "runner.py", "config.json": ROOT / "config.json",
               "tests/test_offline.py": tests / "test_offline.py",
               "finalize.py": NATIVE / "finalize.py", "saved_due_care.py": NATIVE / "saved_due_care.py",
               "due_care_meter.py": NATIVE / "due_care_meter.py"}
    for name, path in sources.items():
        construction["files"].append({"path": name, "source": str(path.relative_to(REPO)),
                                      "content": path.read_text()})
    construction["measurement_plan"] = {"channels": [item["name"] for item in
                                                 primary["recording_description"]["channels"]],
                                        "source": "original Native frame, actor, contact and camera joins"}
    construction["static_checks"] = ["exact law and cell identity", "four original source cameras",
                                      "20 Hz for 30 seconds", "original pedestrian road survey"]
    construction["termination_rules"] = ["600 original simulation frames", "encoder closure",
                                         "world restoration and Native exit before saved analysis"]
    construction["mechanisms"] = ["surveyed pedestrian crossing", "selected controller response",
                                   "original collision event sensing", "saved source-bound finalizer"]
    write(ROOT / "construction.json", construction)
    plan_path = ROOT / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    plan["camera_plan"] = {"profile": "overview1080-capability", "duration_s": 30,
                           "composition": "synchronized_four_view_primary",
                           "coverage": [{"subject": subject, "interval": "all 30 seconds / 600 frames",
                                         "view": view} for view, subject in (
                                             ("overview", "vehicle and surveyed pedestrian"),
                                             ("approach", "vehicle approach to pedestrian path"),
                                             ("reference_corner", "pedestrian crossing and contact region"),
                                             ("driver_reference", "vehicle response and pedestrian relative position"))]}
    plan["source_observation_mapping"] = {
        item["name"]: {"evidence": "Original source-joined 600-frame saved diagnostic and four-camera review; no legal verdict",
                       "channels": [item["name"]],
                       "source_refs": ["native/selected-a-fixture-recipe.json",
                                       "native/selected-b-fixture-recipe.json",
                                       "native/saved_due_care.py"]}
        for item in plan["observations"]}
    for item in plan["observations"]:
        item["status"] = "cpu_source_bound_original_native_pending"
    for item in plan["cases"]:
        item["planning_status"] = "cpu_prepared_original_native_pending"
    for item in plan["comparisons"]:
        item["status"] = "cpu_prepared_original_native_pending"
        item["audit_gap"] = "Original Native motion, pixels, physical response and legal due-care review remain pending."
    write(plan_path, plan)
    print(json.dumps({"root_case": primary["case_id"], "selected_cases": len(selected)}))


if __name__ == "__main__":
    main()
