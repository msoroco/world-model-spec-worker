import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import native_capture
import saved_delivery
import saved_finalizer
import measurement_contract

SITE = {"fps": 20, "site_source_sha256": "b" * 64,
        "alley_route_source_sha256": "c" * 64,
        "access_aisle_source_sha256": "d" * 64,
        "parking_designation_source_sha256": "e" * 64,
        "municipal_jurisdiction_source_sha256": "f" * 64}


def png():
    out = io.BytesIO()
    Image.new("RGB", (2, 2), (10, 20, 30)).save(out, format="PNG")
    return out.getvalue()


class Actor:
    is_alive = True
    id = 42

    def apply_control(self, control):
        self.control = control

    def get_transform(self):
        return types.SimpleNamespace(location=types.SimpleNamespace(x=1.0, y=0.5))

    def get_velocity(self):
        return types.SimpleNamespace(x=2.0, y=0.0)

    def get_acceleration(self):
        return types.SimpleNamespace(x=-0.5, y=0.0)

    def get_angular_velocity(self):
        return types.SimpleNamespace(z=3.0)


class Adapter:
    world = object()
    marking_reader = None
    parking_reader = None
    signal_reader = None
    conflict_reader = None

    def __init__(self):
        self.frame = 40

    def tick(self):
        frame = self.frame
        self.frame += 1
        return types.SimpleNamespace(frame=frame, timestamp=types.SimpleNamespace(elapsed_seconds=frame / 20))

    def image(self, camera, frame):
        if camera not in native_capture.CAMERAS or frame != self.frame - 1:
            raise AssertionError("camera/source join")
        return {"source_kind": "original_native_camera", "camera_id": camera,
                "sensor_id": "sensor-" + camera, "native_frame": frame,
                "native_time_s": frame / 20, "native_verified": True, "png": png()}


def context(*args):
    snapshot = args[2]
    return {"source_kind": "original_native_context_state", "case_id": args[3],
            "native_frame": snapshot.frame, "native_time_s": snapshot.timestamp.elapsed_seconds,
            "source_sha256": "a" * 64, "straddles_marking": False,
            "time_to_conflict_s": None, "traffic_signal": "none"}


class NativeCaptureTests(unittest.TestCase):
    def test_full_original_sources_and_fail_closed_saved_audit(self):
        case_id = next(iter(native_capture.CASE_PROFILES))
        carla = types.SimpleNamespace(VehicleControl=lambda **kwargs: kwargs)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            with patch.object(native_capture, "sample_from_native", side_effect=context):
                receipt = native_capture.capture(Adapter(), Actor(), carla,
                    SITE, case_id, "person-test", output)
            self.assertEqual(receipt["duration_frames"], 900)
            audit = saved_delivery.audit(output, case_id)
            self.assertEqual(audit["decoded_original_pngs"], 3600)
            self.assertEqual(audit["attention_state"], "unobserved")
            with self.assertRaisesRegex(ValueError, "diagnostic capture"):
                saved_finalizer.finalize(output, case_id)
            finalized = saved_finalizer.finalize(output, case_id, allow_diagnostic=True)
            self.assertEqual(finalized["operation_measurement"]["frame_count"], 900)
            self.assertEqual(finalized["decoded_original_pngs"], 3600)
            self.assertEqual(finalized["attention_state"], "unobserved")
            self.assertEqual(finalized["legal_judgment"], "unresolved")
            contract = ROOT / ("measurement-contract-" + case_id.rsplit("__", 1)[1] + ".json")
            checked = measurement_contract.check(contract, output, finalized)
            self.assertTrue(checked["passed"])
            operation_source = output / "operation.jsonl"
            missing_source = output / "operation.hidden"
            operation_source.rename(missing_source)
            with self.assertRaisesRegex(ValueError, "Missing required source: operation.jsonl"):
                measurement_contract.check(contract, output, finalized)
            missing_source.rename(operation_source)
            operation_source.write_bytes(operation_source.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "original source hash mismatch: operation.jsonl"):
                measurement_contract.check(contract, output, finalized)
            operation_source.write_bytes(operation_source.read_bytes()[:-1])
            measurement_path = output / "saved-measurement.json"
            self.assertEqual(saved_finalizer.main(["--attempt", str(output),
                "--case", case_id, "--output", str(measurement_path),
                "--allow-diagnostic"]), 0)
            self.assertEqual(json.loads(measurement_path.read_text())["case_id"], case_id)
            with self.assertRaisesRegex(ValueError, "already exists"):
                saved_finalizer.main(["--attempt", str(output), "--case", case_id,
                    "--output", str(measurement_path), "--allow-diagnostic"])
            second_case = next(c for c in native_capture.CASE_PROFILES if c != case_id)
            second_output = output / "second"
            second_output.mkdir()
            with patch.object(native_capture, "sample_from_native", side_effect=context):
                native_capture.capture(Adapter(), Actor(), carla, SITE,
                    second_case, "person-test", second_output)
            other_finalized = saved_finalizer.finalize(second_output, second_case,
                                                       allow_diagnostic=True)
            self.assertEqual(other_finalized["case_id"], second_case)
            steady = output if case_id.endswith("__steady_travel") else second_output
            variation = second_output if steady == output else output
            receipt_path = output / "pair-receipt.json"
            with self.assertRaisesRegex(ValueError, "diagnostic capture"):
                saved_delivery.main(["--steady", str(steady), "--variation",
                                     str(variation), "--output", str(receipt_path)])
            self.assertFalse(receipt_path.exists())
            self.assertEqual(saved_delivery.main(["--steady", str(steady),
                "--variation", str(variation), "--output", str(receipt_path),
                "--allow-diagnostic"]), 0)
            pair = json.loads(receipt_path.read_text())
            self.assertTrue(pair["diagnostic_fixture"])
            self.assertEqual(pair["legal_judgment"], "unresolved")
            with self.assertRaisesRegex(ValueError, "already exists"):
                saved_delivery.main(["--steady", str(steady), "--variation",
                                     str(variation), "--output", str(receipt_path),
                                     "--allow-diagnostic"])
            with self.assertRaisesRegex(ValueError, "diagnostic capture"):
                saved_delivery.audit(output, case_id, require_delivery=True)
            image = output / "camera-png" / "0000-front.png"
            image.write_bytes(b"broken")
            with self.assertRaisesRegex(ValueError, "image hash mismatch"):
                saved_delivery.audit(output, case_id)
            with self.assertRaisesRegex(ValueError, "image hash mismatch"):
                saved_finalizer.finalize(output, case_id, allow_diagnostic=True)
            with self.assertRaisesRegex(ValueError, "image hash mismatch"):
                saved_delivery.audit_comparison({case_id: output,
                                                  second_case: second_output})

    def test_capture_rejects_nonconforming_duration(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "900-frame"):
                native_capture.capture(None, None, None, {"fps": 20},
                    next(iter(native_capture.CASE_PROFILES)), "person", Path(temporary), 899)

    def test_capture_rejects_stale_camera_packet(self):
        class StaleAdapter(Adapter):
            def image(self, camera, frame):
                packet = super().image(camera, frame)
                packet["native_frame"] -= 1
                return packet

        case_id = next(iter(native_capture.CASE_PROFILES))
        carla = types.SimpleNamespace(VehicleControl=lambda **kwargs: kwargs)
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(native_capture, "sample_from_native", side_effect=context):
                with self.assertRaisesRegex(ValueError, "camera packet frame"):
                    native_capture.capture(StaleAdapter(), Actor(), carla,
                        SITE,
                        case_id, "person-test", Path(temporary))


if __name__ == "__main__":
    unittest.main()
