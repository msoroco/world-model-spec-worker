"""Bundle the two exact Native paths for CPU offline construction checks."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


TEST = '''import json
import unittest
from pathlib import Path
from runner import check
from route_v2 import check as route_check
class Bundle(unittest.TestCase):
    def test_exact_construction(self):
        config=json.loads(Path("config.json").read_text())
        self.assertTrue(check(config)["passed"])
        self.assertTrue(route_check()["passed"])
    def test_unprepared_candidate_rejected(self):
        config=json.loads(Path("config.json").read_text())
        config["candidate_id"]="fallback1"
        with self.assertRaises(ValueError): check(config)
'''


def main():
    base = json.loads((HERE / "current-v2-primary-construction.json").read_text())
    old_config = json.loads(next(item["content"] for item in base["files"]
                                 if item["path"] == "config.json"))
    recording = dict(base["recording_description"])
    recording["context_inputs"] = [
        {"name": "native_facility_readback", "unit": "structured",
         "method": "original Native map lane readback"},
        {"name": "subsection3_conflict_context", "unit": "structured",
         "method": "original conflict actor readback"}]
    recording["limitations"] = ["Official designation and legal exception remain for independent review",
                                "Synthetic fixtures prove source shape only"]
    cameras = [("overview", 1920, 1080, 92, "world"),
               ("approach", 1280, 720, 86, "world"),
               ("reference_corner", 1280, 720, 78, "world"),
               ("driver_reference", 1280, 720, 88, "ego")]
    entries = []
    for suffix, route_suffix in (("controlled_1", "outside_cycle_lane"),
                                 ("controlled_2", "within_cycle_lane")):
        case_id = HERE.name + "__" + suffix
        config = dict(old_config)
        config.update(case_id=case_id, selected_case_id=case_id,
                      case={"case_id": case_id}, case_suffix=route_suffix,
                      supported_case_ids=[case_id], candidate_id="primary",
                      status="unselected_native_draft", recording_description=recording,
                      cameras=[{"name": name, "width": width, "height": height,
                                "fov_deg": fov, "pose_strategy": attach, "fps": 20}
                               for name, width, height, fov, attach in cameras])
        files = [("runner.py", "native/native_capture_v2.py"),
                 ("facility.py", "native/facility.py"),
                 ("route_v2.py", "native/route_v2.py"),
                 ("measure_selected.py", "native/measure_selected.py"),
                 ("finalize.py", "native/finalize_selected.py")]
        embedded = [{"path": name, "content": (HERE / source).read_text()}
                    for name, source in files]
        embedded += [{"path": "config.json", "content": json.dumps(config, indent=2, sort_keys=True) + "\n"},
                     {"path": "tests/test_native_bundle.py", "content": TEST}]
        construction = {"case_id": case_id, "cell_id": "C111250",
                        "law_id": "NRS-484B-270-4", "actor": "motor_vehicle_driver",
                        "entrypoint": "runner.py", "files": embedded,
                        "recording_description": recording,
                        "measurement_plan": {"source": "original Native body, map and exception context"},
                        "static_checks": ["authored crossing and sustained occupancy routes",
                                          "four synchronized cameras at pinned sizes"],
                        "termination_rules": ["600 Native frames; fail on camera/restore error"],
                        "mechanisms": ["OpenDRIVE bicycle facility", "same conflict vehicle",
                                       "original body overlap measurement"],
                        "status": "unselected_native_draft"}
        filename = "draft-native-" + suffix + "-construction.json"
        path = HERE / filename; write(path, construction)
        contract_name = "draft-native-" + suffix + "-measurement-contract.json"
        write(HERE / contract_name, {"format": "worker-measurement-contract",
            "case_id": case_id,
            "requirements": [{"disposition_index": 0, "requirement": "NRS-484B-270-4",
                "source": "NRS 484B.270(4)",
                "output_key": "cycle_lane_intersection_measurement",
                "method": "measure_original_native_cycle_lane", "value_type": "object",
                "kind": "measured", "inputs": ["facility-context.json",
                    "subsection3-context.json", "body-history.jsonl", "trace.jsonl",
                    "video_frames.jsonl", "capture/evidence.jsonl"]}],
            "negative": {"remove": ["body-history.jsonl"],
                         "error_contains": "Missing required source: body-history.jsonl"},
            "status": "unselected_contract_draft"})
        entries.append({"case_id": case_id, "id": "primary",
                        "kind": "draft_not_selected", "construction": filename,
                        "construction_sha256": sha(path),
                        "measurement_contract": contract_name,
                        "measurement_procedure": {"entrypoint": "finalize.py"},
                        "fixture_recipe": str((HERE / ("native-diagnostic-" + suffix + "-recipe.json")).relative_to(REPO)),
                        "recording_description": recording,
                        "candidates": [],
                        "candidate_risk": {"status": "physical",
                                           "reason": "Motion and camera coverage require local review"}})
    manifest = HERE / "draft-native-manifest.json"
    batch = json.loads((REPO / "batch.json").read_text())
    write(manifest, {"format": "worker-unselected-draft-construction-manifest-v1",
                     "assignment_id": HERE.name,
                     "runtime_manifest_sha256": batch["runtime"]["source_manifest_sha256"],
                     "status": "draft_not_selected", "cases": entries})
    print(json.dumps({"manifest_sha256": sha(manifest),
                      "construction_sha256": {e["case_id"]: e["construction_sha256"]
                                              for e in entries}}))


if __name__ == "__main__":
    main()
