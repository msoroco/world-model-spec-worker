import io
import hashlib
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
from attention_sweep_capture import AttentionSweepCapture

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
    def test_original_interior_stream_joins_selected_capture_and_saved_audit(self):
        case_id = next(iter(native_capture.CASE_PROFILES))
        carla = types.SimpleNamespace(VehicleControl=lambda **kwargs: kwargs)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            stage = output / "interior-sources"
            stage.mkdir()
            records = {
                "municipal_jurisdiction": {"format": "diagnostic-municipal-source"},
                "original_site": {"format": "diagnostic-site-source"},
                "interior_sensor": {"format": "reviewed-original-interior-sensor",
                                    "native_verified": True, "sensor_id": "diagnostic-interior-1",
                                    "observable": "original_eyes_off_road_duration_s",
                                    "frame_join": "original_native_frame", "sampling_rate_hz": 20},
                "control_feasibility": {"format": "reviewed-attention-control-feasibility",
                                        "native_verified": True, "minimum_s": 0,
                                        "maximum_s": 4, "resolution_s": 2},
            }
            sources = {}
            for key, document in records.items():
                path = stage / (key + ".json")
                path.write_text(json.dumps(document) + "\n")
                sources[key] = {"path": path.name,
                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                "citation": "CPU diagnostic fixture", "review_status": "reviewed"}
            packet = stage / "packet.json"
            packet.write_text(json.dumps({
                "format": "worker-reviewed-attention-sweep", "assignment_id": ROOT.name,
                "law_id": "LVMC-11-22-010", "diagnostic_fixture": True,
                "sources": sources,
                "axis": {"variable": "interior_distraction_target_s",
                         "observable": "original_eyes_off_road_duration_s", "unit": "s",
                         "min": 0, "max": 4, "spacing": 2,
                         "measurement": {"method": "original interior sensor cumulative duration history",
                                         "statistic": "max",
                                         "time_window": "full original 45-second alley operation"},
                         "range_rationale": "diagnostic fixture", "spacing_rationale": "diagnostic fixture"}
            }) + "\n")
            interior = AttentionSweepCapture(packet, case_id, 0, allow_diagnostic=True)
            sensor_sha = sources["interior_sensor"]["sha256"]

            class InteriorAdapter(Adapter):
                def set_interior_attention(self, actor, selected, index, sensor, requested):
                    return {"source_kind": "original_native_interior_control", "case_id": selected,
                            "frame_index": index, "sensor_id": sensor,
                            "sensor_source_sha256": sensor_sha,
                            "requested_eyes_off_road": requested, "native_verified": True}

                def read_interior(self, actor, snapshot, sensor):
                    return {"source_kind": "original_native_interior", "case_id": case_id,
                            "native_frame": snapshot.frame,
                            "native_time_s": snapshot.timestamp.elapsed_seconds,
                            "sensor_id": sensor, "sensor_source_sha256": sensor_sha,
                            "eyes_off_road": snapshot.frame < 42, "native_verified": True}

            with patch.object(native_capture, "sample_from_native", side_effect=context):
                receipt = native_capture.capture(
                    InteriorAdapter(), Actor(), carla, SITE, case_id,
                    "person-test", output, attention_capture=interior)
            self.assertEqual(receipt["interior_capture"]["measured"][
                "original_eyes_off_road_duration_s"], .1)
            audited = saved_delivery.audit(output, case_id)
            self.assertEqual(audited["interior_source_audit"]["measured_duration_s"], .1)
            self.assertEqual(audited["attention_state"], "unresolved")
            stream = output / "interior-original.jsonl"
            raw = stream.read_bytes()
            stream.write_bytes(raw.replace(b'"native_frame": 40', b'"native_frame": 50', 1))
            with self.assertRaisesRegex(ValueError, "original interior sensor source changed"):
                saved_delivery.audit(output, case_id)

    def test_pipeline_collector_joins_same_original_ticks(self):
        case_id = next(iter(native_capture.CASE_PROFILES))
        carla = types.SimpleNamespace(VehicleControl=lambda **kwargs: kwargs)
        calls = []
        class Pipeline:
            def capture(self, frame, time_s):
                calls.append((frame, time_s))
                return {"frame": frame, "time_s": time_s}
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(native_capture, "FRAMES", 2), \
                    patch.object(native_capture, "sample_from_native", side_effect=context):
                native_capture.capture(Adapter(), Actor(), carla, SITE, case_id,
                                       "person-test", Path(temporary), frames=2,
                                       pipeline_capture=Pipeline())
        self.assertEqual(calls, [(40, 2.0), (41, 2.05)])

    def test_pipeline_collector_frame_mismatch_rejected(self):
        case_id = next(iter(native_capture.CASE_PROFILES))
        carla = types.SimpleNamespace(VehicleControl=lambda **kwargs: kwargs)
        class Pipeline:
            def capture(self, frame, time_s):
                return {"frame": frame + 1, "time_s": time_s}
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(native_capture, "FRAMES", 2), \
                    patch.object(native_capture, "sample_from_native", side_effect=context):
                with self.assertRaisesRegex(ValueError, "PipelineCapture original frame/time"):
                    native_capture.capture(Adapter(), Actor(), carla, SITE, case_id,
                                           "person-test", Path(temporary), frames=2,
                                           pipeline_capture=Pipeline())

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
            frame_map_path = output / "camera-frame-map.jsonl"
            capture_path = output / "capture.json"
            original_map = frame_map_path.read_bytes()
            original_capture = capture_path.read_bytes()
            frame_rows = [json.loads(line) for line in original_map.splitlines()]
            frame_rows[5]["cameras"]["alley_approach"]["sensor_id"] = "replacement-alley-approach"
            altered_map = "".join(json.dumps(row) + "\n" for row in frame_rows).encode()
            frame_map_path.write_bytes(altered_map)
            capture_meta = json.loads(original_capture)
            capture_meta["source_sha256"]["camera_frame_map"] = hashlib.sha256(altered_map).hexdigest()
            capture_path.write_text(json.dumps(capture_meta))
            with self.assertRaisesRegex(ValueError, "camera sensor identity changed"):
                saved_delivery.audit(output, case_id)
            frame_map_path.write_bytes(original_map)
            capture_path.write_bytes(original_capture)
            capture_meta = json.loads(original_capture)
            capture_meta["diagnostic_fixture"] = False
            capture_path.write_text(json.dumps(capture_meta))
            with self.assertRaisesRegex(ValueError, "delivery dimensions differ"):
                saved_delivery.audit(output, case_id, require_delivery=True)
            capture_path.write_bytes(original_capture)
            image = output / "camera-png" / "0000-overview.png"
            original_image = image.read_bytes()
            alias = output / "alias-original.png"
            alias.write_bytes(original_image)
            image.unlink()
            image.symlink_to(alias)
            with self.assertRaisesRegex(ValueError, "symlinked"):
                saved_delivery.audit(output, case_id)
            image.unlink()
            image.write_bytes(original_image)
            original_operation = operation_source.read_bytes()
            missing_source.write_bytes(original_operation)
            operation_source.unlink()
            operation_source.symlink_to(missing_source)
            with self.assertRaisesRegex(ValueError, "symlinked"):
                saved_delivery.audit(output, case_id)
            operation_source.unlink()
            operation_source.write_bytes(original_operation)
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

    def test_capture_rejects_camera_sensor_switch(self):
        class SwitchedAdapter(Adapter):
            def image(self, camera, frame):
                packet = super().image(camera, frame)
                if camera == "alley_approach" and frame >= 45:
                    packet["sensor_id"] = "replacement-alley-approach"
                return packet

        case_id = next(iter(native_capture.CASE_PROFILES))
        carla = types.SimpleNamespace(VehicleControl=lambda **kwargs: kwargs)
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(native_capture, "sample_from_native", side_effect=context):
                with self.assertRaisesRegex(ValueError, "sensor identity changed"):
                    native_capture.capture(SwitchedAdapter(), Actor(), carla,
                        SITE, case_id, "person-test", Path(temporary))
            self.assertFalse((Path(temporary) / "capture.json").exists())


if __name__ == "__main__":
    unittest.main()
