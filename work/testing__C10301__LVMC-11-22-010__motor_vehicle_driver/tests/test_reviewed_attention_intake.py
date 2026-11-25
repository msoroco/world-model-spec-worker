import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("reviewed_attention_intake", ROOT / "reviewed_attention_intake.py")
intake = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(intake)
SCRATCH = Path.cwd() / ".runtime-work" / "c10301-reviewed-attention-tests"
SCRATCH.mkdir(parents=True, exist_ok=True)


class ReviewedAttentionIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.packet_path = self.root / "packet.json"
        records = {
            "municipal_jurisdiction": {"format": "reviewed-municipal-jurisdiction"},
            "original_site": {"format": "reviewed-original-alley-site"},
            "interior_sensor": {"format": "reviewed-original-interior-sensor", "native_verified": True,
                                "sensor_id": "interior-1", "observable": "original_eyes_off_road_duration_s",
                                "frame_join": "original_native_frame", "sampling_rate_hz": 20},
            "control_feasibility": {"format": "reviewed-attention-control-feasibility", "native_verified": True,
                                    "minimum_s": 0, "maximum_s": 4, "resolution_s": 2},
        }
        sources = {}
        for key, content in records.items():
            path = self.root / (key + ".json")
            path.write_text(json.dumps(content) + "\n")
            sources[key] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "citation": "synthetic test source", "review_status": "reviewed"}
        self.packet = {"format": "worker-reviewed-attention-sweep", "assignment_id": intake.ASSIGNMENT,
                       "law_id": intake.LAW, "diagnostic_fixture": True, "sources": sources,
                       "axis": {"variable": "interior_distraction_target_s",
                                "observable": "original_eyes_off_road_duration_s", "unit": "s",
                                "min": 0, "max": 4, "spacing": 2,
                                "measurement": {"method": "original interior sensor cumulative duration history",
                                                "statistic": "max",
                                                "time_window": "full original 45-second alley operation"},
                                "range_rationale": "synthetic test only",
                                "spacing_rationale": "synthetic test only"}}
        self.write_packet()

    def write_packet(self):
        self.packet_path.write_text(json.dumps(self.packet) + "\n")

    def test_diagnostic_shape_is_not_production_authority(self):
        result = intake.validate(self.packet_path, allow_diagnostic=True)
        self.assertEqual(result["legal_judgment"], "unresolved")
        self.assertTrue(result["diagnostic_fixture"])
        with self.assertRaisesRegex(ValueError, "diagnostic attention packet"):
            intake.validate(self.packet_path)

    def test_rejects_changed_source_bytes_and_missing_review(self):
        (self.root / "interior_sensor.json").write_text("{}\n")
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            intake.validate(self.packet_path, allow_diagnostic=True)
        self.packet["sources"]["municipal_jurisdiction"]["review_status"] = "draft"
        self.write_packet()
        with self.assertRaisesRegex(ValueError, "reviewed source required"):
            intake.validate(self.packet_path, allow_diagnostic=True)

    def test_rejects_unsourced_axis_and_nonphysical_grid(self):
        self.packet["axis"]["observable"] = "kin.yaw_rate"
        self.write_packet()
        with self.assertRaisesRegex(ValueError, "interior attention axis"):
            intake.validate(self.packet_path, allow_diagnostic=True)
        self.packet["axis"]["observable"] = "original_eyes_off_road_duration_s"
        self.packet["axis"]["max"] = 2
        self.write_packet()
        with self.assertRaisesRegex(ValueError, "three feasible levels"):
            intake.validate(self.packet_path, allow_diagnostic=True)

    def test_rejects_unverified_sensor_or_feasibility(self):
        sensor = self.root / "interior_sensor.json"
        data = json.loads(sensor.read_text())
        data["frame_join"] = "fixture_index"
        sensor.write_text(json.dumps(data) + "\n")
        self.packet["sources"]["interior_sensor"]["sha256"] = hashlib.sha256(sensor.read_bytes()).hexdigest()
        self.write_packet()
        with self.assertRaisesRegex(ValueError, "original-frame interior join"):
            intake.validate(self.packet_path, allow_diagnostic=True)
        data["frame_join"] = "original_native_frame"
        sensor.write_text(json.dumps(data) + "\n")
        self.packet["sources"]["interior_sensor"]["sha256"] = hashlib.sha256(sensor.read_bytes()).hexdigest()
        feasibility = self.root / "control_feasibility.json"
        levels = json.loads(feasibility.read_text())
        levels["maximum_s"] = 5
        feasibility.write_text(json.dumps(levels) + "\n")
        self.packet["sources"]["control_feasibility"]["sha256"] = hashlib.sha256(feasibility.read_bytes()).hexdigest()
        self.write_packet()
        with self.assertRaisesRegex(ValueError, "axis differs"):
            intake.validate(self.packet_path, allow_diagnostic=True)
