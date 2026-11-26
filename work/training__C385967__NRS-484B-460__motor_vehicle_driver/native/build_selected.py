"""Materialize exact selected Native bundles from the two scoped drafts."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent.name
ROOT = HERE.parents[2]
SIBLING = HERE.parent.parent / "training__C385967__LVMC-11-52-070__motor_vehicle_driver"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_text(value):
    return json.dumps(value, indent=2, allow_nan=False) + "\n"


def main():
    entries = []
    proposal_cases = []
    camera_source = json.loads((SIBLING / "native/condition_a-primary-construction.json").read_text())
    camera_config = json.loads(next(item["content"] for item in camera_source["files"]
                                    if item["path"] == "config.json"))
    for letter, heading in (("a", 45), ("b", 70)):
        source = json.loads((HERE / f"condition_{letter}-construction.json").read_text())
        case_id = source["case_id"]
        config = json.loads(next(item["content"] for item in source["files"]
                                 if item["path"] == "config.json"))
        config.update({"layout": "one_way_road", "maneuver": "angle_park",
            "control": "angle_parking_designation", "frames": 600,
            "required_atoms": ["kin.heading", "kin.speed"], "source_packets": [],
            "cameras": camera_config["cameras"],
            "parking_brake_mode": "hand_brake",
            "observed_activity_request": "parked",
            "physical_completion": {}, "physical_verified": False,
            "legal_verdict": None})
        channels = ["dev.regulatory_sign", "dev.governs", "st.parking_space",
            "drv.standing_or_parked", "kin.heading", "kin.speed", "st.road_edge",
            "rel.occupies", "native_body_pose", "camera_frame_join"]
        description = {"channels": [{"name": name, "unit": "structured",
            "sampling_rate_hz": 20,
            "method": "Original Native actor, map, device or camera-frame source readback",
            "time_window": "all 600 frames / 30 seconds",
            "reference_frame": "original Native frame and elapsed time",
            "uncertainty": "actual device/curb pixels and physical completion require independent review"}
            for name in channels],
            "context_inputs": [{"name": "official_device", "unit": "structured",
                "method": "Native OpenDRIVE readback joined to authored signal; authority/pixels unverified"},
                {"name": "road_geometry", "unit": "structured",
                 "method": "Native map and curb edge readback; actual pixels unverified"}],
            "limitations": ["No legal angle tolerance inferred from an engineering measurement",
                "No physical or legal acceptance from CPU fixtures"]}
        config["recording_description"] = description
        config["case"] = {"case_id": case_id, "recording_description": description}
        files = [{"path": "config.json", "content": json_text(config)}]
        for name in ("selected_runner.py", "capture.py", "cameras.py",
                     "angle-bay-road.xodr", "saved_angle.py", "finalize.py"):
            files.append({"path": "runner.py" if name == "selected_runner.py" else name,
                          "content": (HERE / name).read_text(),
                          "source": str((HERE / name).relative_to(HERE.parents[2]))})
        test = '''import copy\nimport json\nimport unittest\nfrom pathlib import Path\nfrom capture import check\n\nclass SelectedContract(unittest.TestCase):\n    def setUp(self): self.config=json.loads(Path("config.json").read_text())\n    def test_exact(self): self.assertEqual(check(self.config)["frames"],600)\n    def test_missing_device(self):\n        bad=copy.deepcopy(self.config);bad["device_indicated_angle_deg"]=None\n        with self.assertRaisesRegex(ValueError,"device"): check(bad)\n    def test_missing_camera(self):\n        bad=copy.deepcopy(self.config);bad["cameras"].pop()\n        with self.assertRaisesRegex(ValueError,"Four named"): check(bad)\n    def test_short_window(self):\n        bad=copy.deepcopy(self.config);bad["duration_frames"]=599\n        with self.assertRaisesRegex(ValueError,"30-second"): check(bad)\n'''
        files.append({"path": "tests/test_offline.py", "content": test})
        construction = {"format": "worker-inline-construction", "case_id": case_id,
            "law_id": "NRS-484B-460", "cell_id": "C385967",
            "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
            "files": files, "recording_description": description,
            "status": "selected_native_acquisition_cpu_draft"}
        path = HERE / f"selected-{letter}-construction.json"
        path.write_text(json_text(construction))
        entries.append({"case_id": case_id,
            "construction": path.name, "construction_sha256": sha(path)})
        proposal_cases.append({"case_id": case_id, "target_type": "planned_delivery_comparison",
            "recording_description": description, "selection_targets": ["full-train"],
            "source_branch": "Device-indicated parking angle", "gap_ids": ["g-angle-device"]})
        contract = {"format": "worker-measurement-contract", "case_id": case_id,
            "requirements": [{"disposition_index": 0, "requirement": "text-0",
                "source": "NRS 484B.460", "output_key": "at_rest_angle_to_curb",
                "method": "measure_at_rest_angle", "value_type": "number",
                "kind": "measured", "inputs": ["native_samples.jsonl",
                    "body_history.jsonl", "video_frames.jsonl", "official_device.json",
                    "road_geometry.json", "parking_context.json"]},
                {"disposition_index": 1, "requirement": "reviewed-scope-0",
                 "source": "inputs/planning/focused-coverage-20261016-v1/coverage-witnesses.json",
                 "output_key": "official_device_angle",
                 "method": "measure_official_device_angle", "value_type": "number",
                 "kind": "measured", "inputs": ["official_device.json"]}],
            "negative": {"remove": ["official_device.json"],
                "error_contains": "Missing required source: official_device.json"}}
        (HERE / f"selected-{letter}-measurement-contract.json").write_text(json_text(contract))
    manifest = {"format": "draft-execution-manifest", "cases": entries}
    (HERE / "selected-draft-manifest.json").write_text(json_text(manifest))
    proposal_folder = HERE.parent / "proposals"
    proposal_folder.mkdir(exist_ok=True)
    (proposal_folder / "cases.json").write_text(json_text({"assignment_id": ASSIGNMENT,
        "cases": proposal_cases}))
    plan_path = HERE.parent / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    plan["requirement_dispositions"][1].update(status="selected_required",
        evidence_or_gap="Two exact angle cases compare an indicated 45-degree heading with a 70-degree at-rest heading; original device/curb pixels remain for local review.",
        case_ids=[case["case_id"] for case in proposal_cases])
    plan_path.write_text(json_text(plan))
    compatibility = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
        "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
        "cases": [{"case_id": item["case_id"], "kind": "delivery", "id": "primary",
            "construction": "native/" + item["construction"],
            "construction_sha256": item["construction_sha256"],
            "measurement_contract": "native/selected-" + suffix + "-measurement-contract.json",
            "measurement_procedure": {"entrypoint": "finalize.py"},
            "fixture_recipe": "work/" + ASSIGNMENT + "/native/selected-" + suffix + "-fixture-recipe.json"}
            for item, suffix in zip(entries, ("a", "b"))]}
    (HERE.parent / "selected-compat-manifest.json").write_text(json_text(compatibility))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
