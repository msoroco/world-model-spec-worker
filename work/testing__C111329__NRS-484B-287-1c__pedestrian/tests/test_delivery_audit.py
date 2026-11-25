import copy
import hashlib
from io import BytesIO
import json
import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from delivery_audit import CASES, audit_delivery
from comparison_audit import compare_delivery_audits
from native_observation import CAMERAS, capture_observation
from video_sources import encode_original_cameras
import test_native_observation


class ExactDeliveryAuditTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_native_observation.ObservationTests("test_original_capture_and_saved_crossing")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        image = BytesIO()
        Image.new("RGB", (8, 6), (30, 60, 90)).save(image, format="PNG")
        payload = image.getvalue()
        self.readers = {name: lambda frame, payload=payload: {"frame": frame, "png_bytes": payload}
                        for name in CAMERAS}
        self.dimensions = {name: (8, 6) for name in CAMERAS}

    def capture(self, case_id, *, marked=False, inactive=False):
        packet = copy.deepcopy(self.fixture.packet)
        if marked:
            packet["markings"]["marked_crosswalks"] = [{"marking_id": "stripe-1",
                "survey_record_id": "survey-1", "between_edge_station_fraction": [0.45, 0.55]}]
            self.fixture_source().bind(packet, "markings")
        if inactive:
            packet["devices"][1]["operating_intervals_s"] = [[0, 8]]
            self.fixture_source().bind(packet, "devices")
        def read_device(device_id):
            reading = self.fixture.read_device(device_id)
            if inactive and device_id.startswith("east"):
                reading["is_operating"] = False
            return reading
        receipt = capture_observation(self.fixture.world, self.fixture.walker, packet,
            case_id, self.fixture.path, read_device, ticks=5,
            camera_readers=self.readers, camera_dimensions=self.dimensions)
        return packet, receipt

    def fixture_source(self):
        import test_site_geometry
        fixture = test_site_geometry.CrossingSiteTests("test_unmarked_and_marked_comparison")
        fixture.tmp = self.fixture.tmp
        fixture.counter = 20
        return fixture

    def seal(self, receipt, case_id, packet):
        path = self.fixture.path.parent / "native-seal.json"
        source = path.parent / "effective-site-packet.json"
        source.write_text(json.dumps(packet))
        frames = json.loads(self.fixture.path.read_text())["frames"]
        trace = path.parent / "trace.jsonl"
        trace.write_text("".join(json.dumps({"frame": row["frame"],
            "time_s": row["time_s"], "position_m": row["walker_xyz_m"]}) + "\n"
            for row in frames))
        mapping = path.parent / "video_frames.jsonl"
        mapping.write_text("".join(json.dumps({"video_frame": index,
            "carla_frame": row["frame"], "native_frame": row["frame"],
            "time_s": row["time_s"]}) + "\n" for index, row in enumerate(frames)))
        videos = encode_original_cameras(self.fixture.path)
        path.write_text(json.dumps({"case_id": case_id,
            "observation_sha256": receipt["sha256"], "frame_count": 5,
            "restored": True, "errors": [],
            "effective_site_packet_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "trace_sha256": hashlib.sha256(trace.read_bytes()).hexdigest(),
            "video_frame_map_sha256": hashlib.sha256(mapping.read_bytes()).hexdigest(),
            "video_sources_sha256": {name: row["sha256"] for name, row in videos.items()}}))
        return {"kind": "original_native", "case_id": case_id,
            "observation_sha256": receipt["sha256"], "diagnostic_fixture": False,
            "seal_path": str(path), "seal_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def audited(self, case_id, *, marked=False, inactive=False):
        self.fixture.world.frame = 0
        self.fixture.path.unlink(missing_ok=True)
        for archive in self.fixture.path.parent.glob("original.*.png.zip"):
            archive.unlink()
        for video in self.fixture.path.parent.glob("*.mkv"):
            video.unlink()
        packet, receipt = self.capture(case_id, marked=marked, inactive=inactive)
        return audit_delivery(packet, receipt, case_id=case_id,
            native_provenance=self.seal(receipt, case_id, packet), required_frames=5,
            camera_dimensions=self.dimensions)

    def test_three_exact_case_diagnostic_differences(self):
        for case_id, (marked, inactive_expected) in CASES.items():
            with self.subTest(case_id=case_id):
                # Each case has a distinct original attempt and source packet.
                self.fixture.world.frame = 0
                self.fixture.path.unlink(missing_ok=True)
                for archive in self.fixture.path.parent.glob("original.*.png.zip"):
                    archive.unlink()
                packet, receipt = self.capture(case_id, marked=marked,
                                               inactive=not inactive_expected)
                result = audit_delivery(packet, receipt, case_id=case_id,
                    required_frames=5, camera_dimensions=self.dimensions,
                    diagnostic_fixture=True)
                self.assertEqual(result["full_pixel_decodes"], 20)
                self.assertEqual(result["marked_crosswalk_observed"], marked)
                self.assertEqual(result["both_devices_operating_during_crossing"], inactive_expected)
                self.assertIsNone(result["legal_verdict"])

    def test_source_and_native_gate_rejects_missing_or_stale_seal(self):
        case_id = next(iter(CASES))
        packet, receipt = self.capture(case_id)
        with self.assertRaisesRegex(ValueError, "sealed original Native"):
            audit_delivery(packet, receipt, case_id=case_id, required_frames=5,
                           camera_dimensions=self.dimensions)
        seal = self.seal(receipt, case_id, packet)
        result = audit_delivery(packet, receipt, case_id=case_id,
            native_provenance=seal, required_frames=5, camera_dimensions=self.dimensions)
        self.assertIsNotNone(result["native_provenance"])
        Path(seal["seal_path"]).write_text("tampered")
        with self.assertRaisesRegex(ValueError, "seal source hash"):
            audit_delivery(packet, receipt, case_id=case_id,
                native_provenance=seal, required_frames=5, camera_dimensions=self.dimensions)

    def test_case_distinction_rejects_wrong_marking_or_operation(self):
        operating = next(iter(CASES))
        packet, receipt = self.capture(operating, inactive=True)
        with self.assertRaisesRegex(ValueError, "device-operation mismatch"):
            audit_delivery(packet, receipt, case_id=operating, required_frames=5,
                           camera_dimensions=self.dimensions, diagnostic_fixture=True)

    def test_two_sealed_attempt_comparisons_and_fixed_source_rejection(self):
        ids = list(CASES)
        baseline = self.audited(ids[0])
        marked = self.audited(ids[1], marked=True)
        self.assertTrue(compare_delivery_audits("between_intersections_marking",
            baseline, marked)["sealed_attempts_compared"])
        inactive = self.audited(ids[2], inactive=True)
        self.assertTrue(compare_delivery_audits("both_devices_operating",
            baseline, inactive)["sealed_attempts_compared"])
        changed = copy.deepcopy(marked)
        changed["source_sha256"]["map"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "fixed comparison source"):
            compare_delivery_audits("between_intersections_marking", baseline, changed)
        reused = copy.deepcopy(marked)
        reused["source_observation_sha256"] = baseline["source_observation_sha256"]
        with self.assertRaisesRegex(ValueError, "distinct original Native"):
            compare_delivery_audits("between_intersections_marking", baseline, reused)


if __name__ == "__main__":
    unittest.main()
