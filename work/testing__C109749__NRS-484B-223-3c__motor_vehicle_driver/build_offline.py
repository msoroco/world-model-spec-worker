"""Build exact source-gated center-turn-lane construction bundles."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SOURCES = ("center_lane_site.py", "center_lane_measurement.py", "turn_merge_controller.py",
           "native_capture.py", "native_scene.py", "carla_runner.py", "saved_camera_audit.py",
           "saved_finalizer.py", "delivery_audit.py", "comparison_audit.py")
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
RUNNER = '''"""Run one exact Native center-turn-lane attempt from reviewed sources."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from native_capture import VIEWS
from native_scene import run_managed_scene_capture


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    plan_bytes = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact case plan changed")
    plan = json.loads(plan_bytes)
    case = config["selected_case_id"]
    rows = [row for row in plan["cases"] if row["case_id"] == case]
    if len(rows) != 1 or not case.startswith(config["assignment_id"] + "__"):
        raise ValueError("Exact case absent")
    if rows[0]["authored_target_distance_ft"] != config["authored_target_distance_ft"]:
        raise ValueError("Requested merge target changed")
    if (config["law_id"], config["cell_id"], config["actor"]) != (plan["law_id"], plan["cell_id"], plan["actor"]):
        raise ValueError("Assignment identity changed")
    if (config["rate_hz"], config["frame_count"], config["duration_s"]) != (20, 900, 45):
        raise ValueError("Original capture interval changed")
    if [c["name"] for c in config["cameras"]] != list(VIEWS):
        raise ValueError("Four-view camera contract changed")
    return case


def transform_factory(spec):
    import carla
    location = spec["location"]
    rotation = spec["rotation"]
    return carla.Transform(carla.Location(x=location["x"], y=location["y"], z=location["z"]),
                           carla.Rotation(pitch=rotation["pitch"], yaw=rotation["yaw"], roll=rotation["roll"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    case = check()
    if args.check:
        print("exact source-gated center-lane construction passed: " + case)
        return
    root = Path(args.output_dir or "").resolve()
    if not args.output_dir or not root.is_dir():
        raise ValueError("Executor output directory required")
    site_path = os.environ.get("SCENARIO_CENTER_LANE_SITE")
    spawn_path = os.environ.get("SCENARIO_CENTER_LANE_SPAWN_PLAN")
    if not site_path or not spawn_path:
        raise ValueError("Reviewed original site and spawn plan required")
    site_bytes = Path(site_path).read_bytes()
    spawn_bytes = Path(spawn_path).read_bytes()
    site = json.loads(site_bytes)
    fallback_role = json.loads((Path(__file__).resolve().parent / "config.json").read_text()).get("fallback_route_role")
    if fallback_role and json.loads(spawn_bytes).get("reviewed_route_role") != fallback_role:
        raise ValueError("Fallback requires a separately reviewed alternate route")
    plan_binding = {"path": "reviewed-spawn-plan.json", "sha256": hashlib.sha256(spawn_bytes).hexdigest()}
    (root / "reviewed-spawn-plan.json").write_bytes(spawn_bytes)
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    world = client.get_world()
    receipt = run_managed_scene_capture(world=world, attempt_root=root, case_id=case,
        site=site, plan_binding=plan_binding, transform_factory=transform_factory,
        control_factory=carla.VehicleControl)
    (root / "source-gated-capture.json").write_text(json.dumps(receipt, indent=2) + "\\n")

if __name__ == "__main__":
    main()
'''
TEST = '''import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner

class BundleTests(unittest.TestCase):
    def test_exact_preflight(self):
        config = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())
        self.assertEqual(runner.check(), config["selected_case_id"])

    def test_missing_reviewed_source_fails_closed(self):
        import unittest.mock
        with unittest.mock.patch.object(sys, "argv", ["runner.py", "--output-dir", str(Path(__file__).resolve().parents[1])]):
            with self.assertRaisesRegex(ValueError, "Reviewed original site"):
                runner.main()

    def test_fallback_rejects_unreviewed_primary_route(self):
        import os
        import tempfile
        import unittest.mock
        config = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())
        if not config.get("fallback_route_role"):
            return
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR", ".runtime-work")) as temp:
            root = Path(temp)
            site = root / "site.json"
            spawn = root / "spawn.json"
            site.write_text("{}\\n")
            spawn.write_text("{}\\n")
            env = {"SCENARIO_CENTER_LANE_SITE": str(site),
                   "SCENARIO_CENTER_LANE_SPAWN_PLAN": str(spawn)}
            with unittest.mock.patch.dict(os.environ, env), unittest.mock.patch.object(
                    sys, "argv", ["runner.py", "--output-dir", temp]):
                with self.assertRaisesRegex(ValueError, "separately reviewed alternate route"):
                    runner.main()

if __name__ == "__main__":
    unittest.main()
'''


def build():
    plan_path = HERE / "case-plan.json"
    plan_bytes = plan_path.read_bytes()
    plan = json.loads(plan_bytes)
    plan_sha = hashlib.sha256(plan_bytes).hexdigest()
    entries = []
    for row in plan["cases"]:
        case = row["case_id"]
        suffix = case.removeprefix(AID + "__")
        if suffix == case:
            raise ValueError("Foreign case")
        config = {"assignment_id": AID, "law_id": plan["law_id"], "cell_id": plan["cell_id"],
                  "actor": plan["actor"], "selected_case_id": case,
                  "authored_target_distance_ft": row["authored_target_distance_ft"],
                  "recording_description": row["recording_description"],
                  "plan_sha256": plan_sha, "rate_hz": 20, "frame_count": 900, "duration_s": 45,
                  "cameras": [{"name": name, "width": width, "height": height,
                               "fov_deg": 75, "pose_strategy": "reviewed approach and receiving traffic coverage"}
                              for name, width, height in (("overview", 1920, 1080),
                                                          ("approach", 1280, 720),
                                                          ("reference_corner", 1280, 720),
                                                          ("driver_reference", 1280, 720))],
                  "required_atoms": [], "source_packets": [], "diagnostic_only": True}
        files = {name: (HERE / name).read_text() for name in SOURCES}
        files.update({"runner.py": RUNNER, "case-plan.json": plan_bytes.decode(),
                      "config.json": json.dumps(config, indent=2) + "\n",
                      "tests/test_bundle.py": TEST})
        construction = {"law_id": plan["law_id"], "cell_id": plan["cell_id"],
                        "actor": plan["actor"], "case_id": case,
                        "entrypoint": "runner.py", "diagnostic_only": True,
                        "recording_description": row["recording_description"],
                        "files": [{"path": path, "content": content}
                                  for path, content in sorted(files.items())]}
        output = HERE / "cases" / suffix / "construction.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(construction, indent=2) + "\n")
        entries.append({"case_id": case, "construction": str(output.relative_to(HERE)),
                        "construction_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                        "candidate_risk": {"status": "physical", "reason": row["physical_risk_assessment"]["risk"]}})
        alternate = json.loads(json.dumps(construction))
        for item in alternate["files"]:
            if item["path"] == "config.json":
                fallback_config = json.loads(item["content"])
                fallback_config["fallback_route_role"] = "alternate_reviewed_center_lane_entry"
                item["content"] = json.dumps(fallback_config, indent=2) + "\n"
        fallback_path = output.parent / "fallback1-construction.json"
        fallback_path.write_text(json.dumps(alternate, indent=2) + "\n")
        entries[-1]["candidates"] = [{
            "id": "fallback1", "construction": str(fallback_path.relative_to(HERE)),
            "construction_sha256": hashlib.sha256(fallback_path.read_bytes()).hexdigest(),
            "trigger": {"source": "original-attempt/native/capture-receipt.json",
                        "metric": "source-bound center-lane entry and receiving-lane feasibility",
                        "failure_condition": "Primary reviewed route cannot safely spawn both actors or reach the measured merge station"},
            "changed_knobs": ["reviewed_route_role=alternate_reviewed_center_lane_entry",
                              "independently reviewed alternate spawn and entry route"]}]
    (HERE / "execution-manifest.draft.json").write_text(json.dumps({
        "assignment_id": AID, "status": "diagnostic_offline_only_original_site_pending",
        "cases": entries}, indent=2) + "\n")
    print("built", len(entries), "exact constructions")

if __name__ == "__main__":
    build()
