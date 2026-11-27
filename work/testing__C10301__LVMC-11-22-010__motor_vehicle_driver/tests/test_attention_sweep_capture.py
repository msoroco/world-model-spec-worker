import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from attention_sweep_capture import AttentionSweepCapture
from attention_sweep_plan import draft
from attention_source_audit import audit
from owned_runner import _stage_attention_packet
from reviewed_attention_intake import validate as validate_intake

SCRATCH = Path.cwd() / ".runtime-work" / "c10301-attention-capture-tests"
SCRATCH.mkdir(parents=True, exist_ok=True)
CASE = ROOT.name + "__alley_attention_observation-0000"


class Adapter:
    changed = False

    def set_interior_attention(self, actor, case_id, frame_index, sensor_id, requested):
        return {"source_kind": "original_native_interior_control", "case_id": case_id,
                "frame_index": frame_index, "sensor_id": sensor_id,
                "sensor_source_sha256": actor["sensor_sha"],
                "requested_eyes_off_road": not requested if self.changed else requested,
                "native_verified": True}

    def read_interior(self, actor, snapshot, sensor_id):
        return {"source_kind": "original_native_interior", "case_id": CASE,
                "native_frame": snapshot.frame, "native_time_s": snapshot.timestamp.elapsed_seconds,
                "sensor_id": sensor_id, "sensor_source_sha256": actor["sensor_sha"],
                "eyes_off_road": snapshot.frame < 2, "native_verified": True}


class AttentionSweepCaptureTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        records = {
            "municipal_jurisdiction": {"format": "reviewed-municipal-jurisdiction"},
            "original_site": {"format": "reviewed-original-alley-site"},
            "interior_sensor": {"format": "reviewed-original-interior-sensor", "native_verified": True,
                                "sensor_id": "interior-1", "observable": "original_eyes_off_road_duration_s",
                                "frame_join": "original_native_frame", "sampling_rate_hz": 20},
            "control_feasibility": {"format": "reviewed-attention-control-feasibility",
                                    "native_verified": True, "minimum_s": 0,
                                    "maximum_s": 4, "resolution_s": 2},
        }
        sources = {}
        for key, content in records.items():
            path = self.root / (key + ".json")
            path.write_text(json.dumps(content) + "\n")
            sources[key] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "citation": "diagnostic-only source", "review_status": "reviewed"}
        self.actor = {"sensor_sha": sources["interior_sensor"]["sha256"]}
        self.packet = self.root / "packet.json"
        self.packet.write_text(json.dumps({
            "format": "worker-reviewed-attention-sweep", "assignment_id": ROOT.name,
            "law_id": "LVMC-11-22-010", "diagnostic_fixture": True, "sources": sources,
            "axis": {"variable": "interior_distraction_target_s",
                     "observable": "original_eyes_off_road_duration_s", "unit": "s",
                     "min": 0, "max": 4, "spacing": 2,
                     "measurement": {"method": "original interior sensor cumulative duration history",
                                     "statistic": "max",
                                     "time_window": "full original 45-second alley operation"},
                     "range_rationale": "diagnostic only", "spacing_rationale": "diagnostic only"}
        }) + "\n")

    def test_source_gated_capture_and_measurement(self):
        with self.assertRaisesRegex(ValueError, "diagnostic attention packet"):
            AttentionSweepCapture(self.packet, CASE, 2)
        with self.assertRaisesRegex(ValueError, "outside reviewed"):
            AttentionSweepCapture(self.packet, CASE, 1, allow_diagnostic=True)
        capture = AttentionSweepCapture(self.packet, CASE, 2, allow_diagnostic=True)
        for index in range(4):
            capture.request(Adapter(), self.actor, index)
            capture.read(Adapter(), self.actor, SimpleNamespace(
                frame=index, timestamp=SimpleNamespace(elapsed_seconds=index / 20)))
        receipt = capture.finish(self.root, expected_frames=4)
        self.assertEqual(receipt["measured"]["original_eyes_off_road_duration_s"], .1)
        self.assertTrue(receipt["diagnostic_fixture"])
        self.assertFalse(receipt["physical_acceptance_claimed"])
        self.assertEqual(receipt["legal_judgment"], "unresolved")
        with self.assertRaisesRegex(ValueError, "fresh interior"):
            capture.finish(self.root, expected_frames=4)

    def test_control_order_and_readback_fail_closed(self):
        capture = AttentionSweepCapture(self.packet, CASE, 2, allow_diagnostic=True)
        with self.assertRaisesRegex(ValueError, "control readback required"):
            capture.read(Adapter(), self.actor, SimpleNamespace(
                frame=0, timestamp=SimpleNamespace(elapsed_seconds=0)))
        adapter = Adapter()
        adapter.changed = True
        with self.assertRaisesRegex(ValueError, "readback differs"):
            capture.request(adapter, self.actor, 0)
        self.assertEqual(capture.controls, [])
        capture.request(Adapter(), self.actor, 0)
        capture.read(Adapter(), self.actor, SimpleNamespace(
            frame=0, timestamp=SimpleNamespace(elapsed_seconds=0)))
        with self.assertRaisesRegex(ValueError, "complete original"):
            capture.finish(self.root, expected_frames=2)

    def test_source_gated_plan_preserves_unresolved_judgment(self):
        with self.assertRaisesRegex(ValueError, "diagnostic attention packet"):
            draft(self.packet, ROOT / "proposals" / "cases.json")
        result = draft(self.packet, ROOT / "proposals" / "cases.json",
                       allow_diagnostic=True)
        spec = result["sweep_spec"]
        self.assertEqual(spec["status"], "complete")
        self.assertEqual(spec["axes"][0]["observable"],
                         "original_eyes_off_road_duration_s")
        self.assertEqual([spec["axes"][0][key] for key in ("min", "max", "spacing")],
                         [0, 4, 2])
        self.assertEqual(result["legal_judgment"], "unresolved")
        self.assertTrue(result["diagnostic_fixture"])
        self.assertFalse(result["selected_cases_changed"])
        self.assertNotIn("spec_version", spec)

    def test_saved_source_audit_rejects_changes_and_diagnostic_production(self):
        capture = AttentionSweepCapture(self.packet, CASE, 2, allow_diagnostic=True)
        for index in range(4):
            capture.request(Adapter(), self.actor, index)
            capture.read(Adapter(), self.actor, SimpleNamespace(
                frame=100 + index,
                timestamp=SimpleNamespace(elapsed_seconds=10 + index / 20)))
        receipt = capture.finish(self.root, expected_frames=4)
        with self.assertRaisesRegex(ValueError, "diagnostic attention packet"):
            audit(self.root, self.packet, receipt, expected_frames=4)
        checked = audit(self.root, self.packet, receipt, allow_diagnostic=True,
                        expected_frames=4)
        self.assertEqual(checked["original_frames"], 4)
        self.assertEqual(checked["measured_duration_s"], 0)
        self.assertTrue(checked["diagnostic_fixture"])
        control = self.root / "interior-control.jsonl"
        original = control.read_bytes()
        control.write_bytes(original.replace(b'"frame_index": 2', b'"frame_index": 5'))
        with self.assertRaisesRegex(ValueError, "control source changed"):
            audit(self.root, self.packet, receipt, allow_diagnostic=True,
                  expected_frames=4)
        control.write_bytes(original)
        sensor = self.root / "interior-original.jsonl"
        original = sensor.read_bytes()
        sensor.write_bytes(original.replace(b'"native_frame": 102',
                                            b'"native_frame": 105'))
        with self.assertRaisesRegex(ValueError, "sensor source changed"):
            audit(self.root, self.packet, receipt, allow_diagnostic=True,
                  expected_frames=4)
        sensor.write_bytes(original)
        changed = dict(receipt)
        changed["intake_packet_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "intake packet changed"):
            audit(self.root, self.packet, changed, allow_diagnostic=True,
                  expected_frames=4)

    def test_staging_preserves_source_hashes_and_refuses_diagnostic_packet(self):
        expected_site = json.loads(self.packet.read_text())["sources"]["original_site"]["sha256"]
        with self.assertRaisesRegex(ValueError, "diagnostic attention packet"):
            _stage_attention_packet(self.packet, self.root / "attempt", expected_site)
        document = json.loads(self.packet.read_text())
        document["diagnostic_fixture"] = False
        reviewed_shape = self.root / "reviewed-shape-unit-test.json"
        reviewed_shape.write_text(json.dumps(document) + "\n")
        attempt = self.root / "attempt"
        attempt.mkdir()
        with self.assertRaisesRegex(ValueError, "original site differs"):
            _stage_attention_packet(reviewed_shape, attempt, "0" * 64)
        staged = _stage_attention_packet(reviewed_shape, attempt, expected_site)
        intake = validate_intake(staged)
        self.assertFalse(intake["diagnostic_fixture"])
        self.assertEqual(intake["source_sha256"], {
            key: value["sha256"] for key, value in document["sources"].items()})
        with self.assertRaisesRegex(ValueError, "already exists"):
            _stage_attention_packet(reviewed_shape, attempt, expected_site)


if __name__ == "__main__":
    unittest.main()
