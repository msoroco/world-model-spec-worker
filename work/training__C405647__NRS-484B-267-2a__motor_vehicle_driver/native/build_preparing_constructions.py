"""Create two exact source-guarded prospective preparing-case CPU bundles."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
AID = FOLDER.name
TEST = '''import json
import unittest
from pathlib import Path
from preparing_runner import check_config, classify_exact

def source(branch, case):
    row = {"case_id": case, "source_kind": "original_native_observation",
           "subject_approach_source_id": "original:approach",
           "authorized_vehicle_source_id": "original:vehicle",
           "vehicle_kind": "authorized_emergency_vehicle",
           "flashing_equipment_source_id": "original:equipment",
           "flashing_pixel_source_id": "original:lamp-pixels",
           "flashing_qualification_source_id": "original:lamp-review",
           "officer_direction_source_id": "original:officer-review",
           "road_context_source_id": "original:road",
           "weather_context_source_id": "original:weather",
           "already_moving": False, "visible_vehicle_movement": False,
           "visible_driver_hand_signal": False, "officer_directed": False}
    row[branch] = True
    if branch == "visible_vehicle_movement":
        row["movement_pixel_source_id"] = "original:movement-pixels"
    else:
        row["hand_signal_pixel_source_id"] = "original:hand-pixels"
        row["hand_signal_actor_source_id"] = "original:driver"
    return row

class ExactPreparingCase(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path("config.json").read_text())
        self.branch = self.config["activation_branch"]
        self.row = source(self.branch, self.config["case_id"])

    def test_exact_contract(self):
        self.assertFalse(check_config(self.config)["physical_completion_claimed"])

    def test_positive_source_classification(self):
        self.assertEqual(classify_exact(self.config, self.row)["observed_activation_branches"], [self.branch])

    def test_synthetic_rejected(self):
        self.row["source_kind"] = "synthetic_cpu_fixture"
        with self.assertRaisesRegex(ValueError, "Original Native source required"):
            classify_exact(self.config, self.row)

    def test_other_branch_rejected(self):
        self.row["case_id"] = "other"
        with self.assertRaisesRegex(ValueError, "another exact case"):
            classify_exact(self.config, self.row)

    def test_missing_pixel_source_rejected(self):
        self.row.pop("movement_pixel_source_id" if self.branch == "visible_vehicle_movement" else "hand_signal_pixel_source_id")
        with self.assertRaisesRegex(ValueError, "source missing"):
            classify_exact(self.config, self.row)
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan = json.loads((HERE / "preparing-alternative-plan.json").read_text())
    cases = []
    for item in plan["alternatives"]:
        case = item["exact_case_id"]
        branch = item["activation_branch"]
        config = {"case_id": case, "law_id": "NRS-484B-267-2a",
                  "cell_id": "C405647", "actor": "motor_vehicle_driver",
                  "activation_branch": branch, "already_moving": False,
                  "duration_frames": 600, "rate_hz": 20,
                  "required_views": item["required_views"],
                  "original_source_requirements": item["required_original_sources"] + item["required_branch_sources"],
                  "physical_verified": False, "legal_verdict": None}
        files = [{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                 {"path": "runner.py", "content": (HERE / "preparing_runner.py").read_text()},
                 {"path": "preparing_runner.py", "content": (HERE / "preparing_runner.py").read_text()},
                 {"path": "branch_alternatives.py", "content": (HERE / "branch_alternatives.py").read_text()},
                 {"path": "tests/test_exact.py", "content": TEST}]
        construction = {"format": "worker-inline-construction", "assignment_id": AID,
                        "case_id": case, "law_id": "NRS-484B-267-2a", "cell_id": "C405647",
                        "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
                        "files": files,
                        "measurement_plan": {"entrypoint": "runner.py",
                                             "sources": config["original_source_requirements"],
                                             "legal_result": None},
                        "recording_description": {"channels": [], "context_inputs": [],
                                                  "limitations": ["Original source and physical review pending"]},
                        "status": "prospective_source_guarded_cpu_only"}
        path = HERE / "preparing" / branch / "construction.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(construction, indent=2, sort_keys=True) + "\n")
        cases.append({"case_id": case, "kind": "prospective_preparing_cpu",
                      "id": "primary", "construction": str(path.relative_to(HERE)),
                      "construction_sha256": sha(path),
                      "physical_evidence_pending": True})
    manifest = {"format": "worker-execution-manifest", "assignment_id": AID,
                "status": "prospective_cpu_not_delivery_ready", "delivery_ready": False,
                "original_native_observed": False, "cases": cases}
    output = HERE / "preparing-cpu-manifest.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return {"cases": len(cases), "manifest_sha256": sha(output)}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
