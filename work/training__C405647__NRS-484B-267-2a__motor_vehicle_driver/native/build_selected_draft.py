"""Bind current prospective Native code into exact selected CPU draft bundles."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.parent.name
TEST = '''import json
from pathlib import Path
import unittest
from capture_runner import check_config, speed_control

class SelectedDraftTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path("config.json").read_text())

    def test_exact_config_and_full_window(self):
        report = check_config(self.config)
        self.assertEqual(report["frames"], 600)
        self.assertTrue(report["site_survey_pending"])
        self.assertFalse(report["physical_completion_claimed"])

    def test_speed_controller(self):
        self.assertGreater(speed_control(7, 14)["brake"], 0)
        self.assertEqual(speed_control(14, 14)["brake"], 0)

    def test_short_window_rejected(self):
        self.config["duration_frames"] = 599
        with self.assertRaisesRegex(ValueError, "Exact duration"):
            check_config(self.config)
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def build():
    entries = []
    common = ["runner.py", "capture_runner.py", "observed_speed.py", "compare_speed.py"]
    for suffix in ("a", "b"):
        case = AID + "__selected_d6045110__condition_" + suffix
        draft = json.loads((HERE / ("condition_" + suffix + "-construction.json")).read_text())
        config = json.loads(draft["files"][0]["content"])
        config["supported_case_ids"] = [case]
        config["required_atoms"] = []
        config["source_packets"] = []
        config["case"] = case
        files = [{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"}]
        files.extend({"path": name, "content": (HERE / name).read_text()} for name in common)
        files.append({"path": "tests/test_offline.py", "content": TEST})
        construction = {
            "format": "worker-inline-construction", "assignment_id": AID,
            "case_id": case, "law_id": "NRS-484B-267-2a", "cell_id": "C405647",
            "actor": "motor_vehicle_driver", "entrypoint": "runner.py", "files": files,
            "measurement_plan": {"entrypoint": "observed_speed.py",
                                 "sources": ["emergency_observations.jsonl", "video_frames.jsonl",
                                             "capture/evidence.jsonl", "four original camera streams"],
                                 "legal_result": None},
            "recording_description": {
                "case_id": case, "frames": 600, "rate_hz": 20,
                "cameras": [view["name"] for view in config["cameras"]],
                "limitations": ["Original site survey and pixels not available to CPU worker",
                                "Flashing-light qualification and reasonable speed require original review"]},
            "status": "selected_cpu_draft_not_delivery_ready"
        }
        destination = HERE / "selected" / suffix / "construction.json"
        write(destination, construction)
        entries.append({"case_id": case, "kind": "selected_cpu_draft_not_delivery_ready",
                        "construction": str(destination.relative_to(HERE)),
                        "construction_sha256": sha(destination),
                        "candidate_risk": {"status": "physical",
                                           "reason": "Emergency actor approach/passing timing and four-view coverage need original Native readback"},
                        "candidates": [], "delivery_readiness": "incomplete"})
    manifest = {"format": "worker-selected-cpu-draft-manifest-v1", "assignment_id": AID,
                "status": "partial", "cases": entries}
    write(HERE / "selected-draft-manifest.json", manifest)
    return {"case_hashes": {entry["case_id"]: entry["construction_sha256"] for entry in entries},
            "manifest_sha256": sha(HERE / "selected-draft-manifest.json")}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True))
