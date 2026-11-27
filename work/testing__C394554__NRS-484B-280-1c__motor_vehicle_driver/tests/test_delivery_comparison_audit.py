import copy
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fixture_sources import write as write_fixture


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


delivery = module("delivery_audit")
comparison = module("comparison_audit")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value) + "\n")


class AuditTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def fixture(self, phase):
        case = ROOT.name + "__" + phase
        stage = self.root / phase
        stage.mkdir()
        attempt = stage / "attempt"
        attempt.mkdir()
        processed = stage / "processed"
        processed.mkdir()
        write_fixture(attempt, phase)
        config = json.loads((ROOT / "config.json").read_text())
        scene = json.loads((ROOT / "scene.json").read_text())
        config["selected_case_id"] = case
        config["case"]["case_id"] = case
        config["case"]["passenger_phase"] = phase
        scene["case_id"] = case
        scene["passenger_phase"] = phase
        write(attempt / "config.json", config)
        write(attempt / "scene.json", scene)
        write(attempt / "capture-seal.json",
              {"events": ["capture_finished", "encoders_closed", "restoration_verified"],
               "sources": {name: sha(attempt / name) for name in delivery.ORIGINAL}})
        write(attempt / "native-exit.json",
              {"event": "native_exit", "capture_seal_sha256": sha(attempt / "capture-seal.json")})
        write(attempt / "owner-release.json",
              {"event": "owner_released", "operator_attested": True,
               "native_exit_sha256": sha(attempt / "native-exit.json")})
        write(attempt / "result.json",
              {"case_id": case, "setup_confirmed": True,
               "behavior_attempted": True, "maneuver_completed": True})
        (processed / "raw.mkv").write_bytes(b"diagnostic media bytes only")
        processing = processed / "processing.json"
        write(processing, {"format": "worker-saved-processing", "passed": True,
                           "recorded_only": True, "result": str(attempt / "result.json"),
                           "result_sha256": sha(attempt / "result.json"),
                           "analysis_directory": str(processed)})
        write(attempt / "pixel-review.json",
              {"format": "independent-transit-pixel-review", "case_id": case,
               "reviewer": "diagnostic test reviewer", "video_sha256": sha(processed / "raw.mkv"),
               "frame_map_sha256": sha(attempt / "video_frames.jsonl"),
               "stop_prop_visible": True, "bus_visible": True,
               "pedestrian_visible": True,
               "actual_bus_door_visible": phase == "boarding_bus",
               "pedestrian_ingress_visible": phase == "boarding_bus",
               "fixture_only": True})
        decode = processed / "decode.json"
        write(decode, {"fixture_only": True})
        return attempt, processing, decode, case

    def audit(self, bundle):
        return delivery.audit(*bundle, media_verify=lambda *a, **k: True,
                              fixture_mode=True)

    def test_fixture_review_rejected_in_production(self):
        bundle = self.fixture("boarding_bus")
        with self.assertRaisesRegex(ValueError, "fixture-only pixel review"):
            delivery.audit(*bundle, media_verify=lambda *a, **k: True)

    def test_positive_source_bound_waiting_and_boarding(self):
        waiting = self.audit(self.fixture("waiting_at_stop"))
        boarding = self.audit(self.fixture("boarding_bus"))
        self.assertEqual(waiting["measurement"]["door_approach_m"], 0)
        self.assertGreater(boarding["measurement"]["door_approach_m"], 0)
        compared = comparison.audit(waiting, boarding)
        self.assertTrue(compared["passed"])
        self.assertFalse(compared["actual_boarding_reviewed"])
        self.assertIsNone(compared["legal_verdict"])

    def test_missing_or_stale_originals_rejected(self):
        bundle = self.fixture("boarding_bus")
        attempt = bundle[0]
        (attempt / "transit-site.json").write_text("changed")
        with self.assertRaisesRegex(ValueError, "sealed original missing or changed"):
            self.audit(bundle)

    def test_pixel_review_cannot_be_omitted_or_misbinding(self):
        bundle = self.fixture("boarding_bus")
        attempt = bundle[0]
        (attempt / "pixel-review.json").unlink()
        with self.assertRaises(FileNotFoundError):
            self.audit(bundle)
        review = {"format": "independent-transit-pixel-review", "case_id": bundle[3],
                  "reviewer": "diagnostic test reviewer", "video_sha256": "stale",
                  "frame_map_sha256": sha(attempt / "video_frames.jsonl"),
                  "stop_prop_visible": True, "bus_visible": True,
                  "pedestrian_visible": True, "actual_bus_door_visible": True,
                  "pedestrian_ingress_visible": True}
        write(attempt / "pixel-review.json", review)
        with self.assertRaisesRegex(ValueError, "pixel review absent or stale"):
            self.audit(bundle)

    def test_comparison_rejects_changed_setup_and_unmeasured_motion(self):
        waiting = self.audit(self.fixture("waiting_at_stop"))
        boarding = self.audit(self.fixture("boarding_bus"))
        bad = copy.deepcopy(boarding)
        bad["fixed_transit_geometry"]["bus_position_m"][1] += 1
        with self.assertRaisesRegex(ValueError, "placement differs"):
            comparison.audit(waiting, bad)
        bad = copy.deepcopy(boarding)
        bad["measurement"]["door_approach_m"] = 0
        with self.assertRaisesRegex(ValueError, "difference not observed"):
            comparison.audit(waiting, bad)


if __name__ == "__main__":
    unittest.main()
