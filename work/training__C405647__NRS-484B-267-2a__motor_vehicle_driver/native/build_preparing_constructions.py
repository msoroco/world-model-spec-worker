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
        self.assertIn(self.config["other_vehicle_start_frame"], (100, 120))

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
    dispositions = json.loads((FOLDER / "case-plan.json").read_text())["requirement_dispositions"]
    original_inputs = ["preparing_observations.jsonl", "video_frames.jsonl", "trace.jsonl",
                       "capture/manifest.json", "acquisition-provenance.json",
                       "overview.mkv", "approach.mkv", "reference_corner.mkv",
                       "driver_reference.mkv"]
    method_by_requirement = {"text-0": ("qualifying_approach", "measure_qualifying_approach"),
                             "text-1": ("speed_response", "measure_speed_response"),
                             "text-2": ("preparing_source", "measure_preparing_source"),
                             "text-3": ("vehicle_movement", "measure_vehicle_movement"),
                             "text-4": ("driver_hand_signal", "measure_driver_hand_signal")}
    cases = []
    for item in plan["alternatives"]:
        case = item["exact_case_id"]
        branch = item["activation_branch"]
        config = {"case_id": case, "law_id": "NRS-484B-267-2a",
                  "selected_case_id": case,
                  "cell_id": "C405647", "actor": "motor_vehicle_driver",
                  "activation_branch": branch, "already_moving": False,
                  "duration_frames": 600, "duration_s": 30, "rate_hz": 20,
                  "cameras": [{"name": name, "fps": 20,
                               "width": 1920 if name == "overview" else 1280,
                               "height": 1080 if name == "overview" else 720}
                              for name in item["required_views"]],
                  "ego_initial_speed_mps": 14, "ego_target_speed_mps": 7,
                  "other_vehicle_start_frame": 120,
                  "other_vehicle_speed_mps": 1 if branch == "visible_vehicle_movement" else 0,
                  "posted_limit_mps": 15, "visibility_m": 200, "wet_road": False,
                  "required_atoms": [], "source_packets": [],
                  "required_views": item["required_views"],
                  "original_source_requirements": item["required_original_sources"] + item["required_branch_sources"],
                  "physical_verified": False, "legal_verdict": None}
        files = [{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                 {"path": "runner.py", "content": (HERE / "preparing_runner.py").read_text()},
                 {"path": "preparing_runner.py", "content": (HERE / "preparing_runner.py").read_text()},
                 {"path": "preparing_finalize.py", "content": (HERE / "preparing_finalize.py").read_text()},
                 {"path": "preparing_movement_capture.py", "content": (HERE / "preparing_movement_capture.py").read_text()},
                 {"path": "preparing_hand_capture.py", "content": (HERE / "preparing_hand_capture.py").read_text()},
                 {"path": "preparing_hand_signal_rig.py", "content": (HERE / "preparing_hand_signal_rig.py").read_text()},
                 {"path": "branch_alternatives.py", "content": (HERE / "branch_alternatives.py").read_text()},
                 {"path": "tests/test_exact.py", "content": TEST}]
        construction = {"format": "worker-inline-construction", "assignment_id": AID,
                        "case_id": case, "law_id": "NRS-484B-267-2a", "cell_id": "C405647",
                        "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
                        "files": files,
                        "measurement_plan": {"entrypoint": "runner.py",
                                             "saved_finalizer": "preparing_finalize.py",
                                             "movement_capture_entrypoint": "preparing_movement_capture.py"
                                             if branch == "visible_vehicle_movement" else None,
                                             "hand_signal_rig": "preparing_hand_signal_rig.py"
                                             if branch == "visible_driver_hand_signal" else None,
                                             "hand_signal_capture_entrypoint": "preparing_hand_capture.py"
                                             if branch == "visible_driver_hand_signal" else None,
                                             "sources": config["original_source_requirements"],
                                             "legal_result": None},
                        "recording_description": {"channels": [{
                            "name": "emergency_speed_and_lamps", "unit": "structured",
                            "method": "Saved original Native actor velocities, lamp readback, and frame/time join",
                            "sampling_rate_hz": 20, "time_window": "all 600 frames",
                            "reference_frame": "original Native frame",
                            "uncertainty": "50 ms frame bracket; visual and legal qualification require separate original pixel review"
                        }], "context_inputs": [],
                            "limitations": ["Original source and physical review pending"]},
                        "status": "prospective_source_guarded_cpu_only"}
        path = HERE / "preparing" / branch / "construction.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(construction, indent=2, sort_keys=True) + "\n")
        fallback = json.loads(json.dumps(construction))
        fallback_config = dict(config, other_vehicle_start_frame=100)
        next(file for file in fallback["files"] if file["path"] == "config.json")["content"] = (
            json.dumps(fallback_config, indent=2) + "\n")
        fallback["status"] = "source_guarded_earlier_indication_timing_fallback"
        fallback_path = path.parent / "fallback1/construction.json"
        fallback_path.parent.mkdir(parents=True, exist_ok=True)
        fallback_path.write_text(json.dumps(fallback, indent=2, sort_keys=True) + "\n")
        contract = {"format": "worker-measurement-contract", "requirements": [
            {"disposition_index": index, "requirement": disposition["requirement"],
             "source": disposition["source"], "output_key": method_by_requirement[disposition["requirement"]][0],
             "method": method_by_requirement[disposition["requirement"]][1],
             "value_type": "object", "kind": "measured", "inputs": original_inputs}
            for index, disposition in enumerate(dispositions)
            if disposition["requirement"] in method_by_requirement
            and disposition["status"] == "selected_required"
            and case in disposition.get("case_ids", [])],
            "negative": {"remove": ["preparing_observations.jsonl"],
                         "error_contains": "Missing required source: preparing_observations.jsonl"}}
        contract_path = path.parent / "measurement-contract.json"
        contract_path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
        cases.append({"case_id": case, "kind": "prospective_preparing_cpu",
                      "id": "primary", "construction": str(path.relative_to(HERE)),
                      "construction_sha256": sha(path),
                      "candidates": [{"id": "fallback1",
                                      "construction": str(fallback_path.relative_to(HERE)),
                                      "construction_sha256": sha(fallback_path)}],
                      "post_capture": "preparing_finalize.py",
                      "independent_source_audit": "preparing_source_audit.py",
                      "measurement_procedure": {"entrypoint": "preparing_finalize.py",
                                                "output_schema": "c405647-preparing-saved-analysis-v1"},
                      "measurement_contract": str(contract_path.relative_to(HERE)),
                      "fixture_recipe": "work/" + AID + "/preparing-recipe-" + branch + ".json",
                      "physical_evidence_pending": True})
    manifest = {"format": "worker-execution-manifest", "assignment_id": AID,
                "runtime_manifest_sha256": sha(HERE.parents[2] / "runtime/SOURCE-MANIFEST.json"),
                "status": "prospective_cpu_not_delivery_ready", "delivery_ready": False,
                "original_native_observed": False, "cases": cases}
    output = HERE / "preparing-cpu-manifest.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    public_entries = []
    for entry in cases:
        public = dict(entry)
        public["construction"] = "native/" + entry["construction"]
        public["measurement_contract"] = "native/" + entry["measurement_contract"]
        public["candidates"] = [dict(candidate, construction="native/" + candidate["construction"])
                                for candidate in entry["candidates"]]
        public_entries.append(public)
    public_manifest = {**manifest, "cases": public_entries}
    (FOLDER / "preparing-compatibility-manifest.json").write_text(
        json.dumps(public_manifest, indent=2, sort_keys=True) + "\n")
    alternate_entries = []
    for entry in public_entries:
        alternate = dict(entry)
        alternate["fixture_recipe"] = "work/" + AID + "/preparing-recipe-" + (
            entry["case_id"].split("__preparing_to_move__", 1)[1]) + "-fallback1.json"
        alternate_entries.append(alternate)
    (FOLDER / "preparing-fallback-compatibility-manifest.json").write_text(
        json.dumps({**manifest, "cases": alternate_entries}, indent=2, sort_keys=True) + "\n")
    return {"cases": len(cases), "manifest_sha256": sha(output)}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
