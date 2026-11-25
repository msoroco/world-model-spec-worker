import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from source_tick_capture import TickCapture, write_capture_identity
from camera_sources import CAMERAS, _verify_raw_bgra_hash, audit_camera_sources, write_camera_sources
from saved_finalizer import finalize


GEOMETRY = {"ego_route_origin_xy_m": [-10, 5], "ego_route_axis_xy": [1, 0],
            "through_route_origin_xy_m": [5, -10], "through_route_axis_xy": [0, 1],
            "ego_entry_station_m": 10,
            "intersection_polygon_xy_m": [[0, 0], [10, 0], [10, 10], [0, 10]]}
CONTEXT = {name: True for name in (
    "yield_sign_governs_approach", "no_marked_stop_line", "no_near_side_crosswalk",
    "no_sidewalk_derived_crosswalk", "through_highway_confirmed", "no_officer_control",
    "no_signal_control", "viewpoint_reviewed")}


def body(x, y):
    return [[x - 1, y - .5], [x + 1, y - .5], [x + 1, y + .5], [x - 1, y + .5]]


def raw(index):
    ego_x = (-9, -5, 0)[index]
    through_y = (-8, -3, 4)[index]
    return {"frame": 100 + index, "time_s": index * .05,
            "ego": {"body_vertices_xy_m": body(ego_x, 5), "velocity_xy_mps": [3 - index, 0]},
            "through_vehicle": {"center_xy_m": [5, through_y],
                                "body_vertices_xy_m": body(5, through_y)},
            "visibility_probe": {"source": "native_raycast", "occluded": index == 0,
                                 "origin_xy_m": [ego_x, 5], "target_xy_m": [5, through_y]},
            "sign_present": True}


def png(color):
    stream = BytesIO()
    Image.new("RGB", (8, 6), color).save(stream, format="PNG")
    return stream.getvalue()


def fixture(attempt):
    capture = TickCapture(attempt, GEOMETRY, CONTEXT)
    frames = []
    for index in range(3):
        row = raw(index)
        capture.append(row)
        frames.append({"frame": row["frame"], "time_s": row["time_s"],
                       "cameras": {name: png((index * 30, camera * 40, 60))
                                   for camera, name in enumerate(CAMERAS)}})
    capture.close()
    construction = attempt.parent / "construction.json"
    construction.write_text('{"case":"nearest_view_response"}\n')
    opendrive = b"<OpenDRIVE>diagnostic map</OpenDRIVE>"
    site = attempt.parent / "reviewed-site.json"
    site.write_text(json.dumps({"review_status": "reviewed",
                                "map_opendrive_sha256": hashlib.sha256(opendrive).hexdigest()}) + "\n")
    write_capture_identity(attempt,
                           "testing__C158208__NRS-484B-257-1__motor_vehicle_driver__nearest_view_response",
                           construction, site, opendrive, diagnostic_fixture=True)
    return frames


class CameraSourcesTests(unittest.TestCase):
    def test_archived_png_reconstructs_opaque_original_bgra(self):
        import hashlib
        original = b"\x00\x00\xff\xff" * (8 * 6)
        _verify_raw_bgra_hash(png("red"), hashlib.sha256(original).hexdigest(), "overview")
        with self.assertRaisesRegex(ValueError, "BGRA source hash differs"):
            _verify_raw_bgra_hash(png("blue"), hashlib.sha256(original).hexdigest(), "overview")

    def test_saved_finalizer_joins_measurement_and_decoded_pixels(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt = Path(directory) / "attempt"
            frames = fixture(attempt)
            write_camera_sources(attempt, frames, diagnostic_fixture=True)
            output = Path(directory) / "report.json"
            report = finalize(attempt, output, diagnostic_fixture=True)
            self.assertEqual(report["measurement"]["first_view"]["index"], 1)
            self.assertEqual(report["measurement"]["intersection_entry"]["index"], 2)
            self.assertEqual(report["decoded_images"], 12)
            self.assertEqual(report["legal_status"], "unresolved")
            self.assertEqual(json.loads(output.read_text()), report)
            with self.assertRaisesRegex(ValueError, "already exists"):
                finalize(attempt, output, diagnostic_fixture=True)

    def test_saved_finalizer_rejects_missing_media_and_false_review_context(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt = Path(directory) / "attempt"
            fixture(attempt)
            with self.assertRaises(FileNotFoundError):
                finalize(attempt, Path(directory) / "report.json", diagnostic_fixture=True)
        with tempfile.TemporaryDirectory() as directory:
            attempt = Path(directory) / "attempt"
            frames = fixture(attempt)
            write_camera_sources(attempt, frames, diagnostic_fixture=True)
            packet_path = attempt / "nearest-view-saved-packet.json"
            packet = json.loads(packet_path.read_text())
            packet["reviewed_context"]["viewpoint_reviewed"] = False
            packet_path.write_text(json.dumps(packet) + "\n")
            with self.assertRaisesRegex(ValueError, "saved packet source hash"):
                finalize(attempt, Path(directory) / "report.json", diagnostic_fixture=True)

    def test_saved_full_decode_joins_every_original_tick_and_camera(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt = Path(directory)
            frames = fixture(attempt)
            manifest = write_camera_sources(attempt, frames, diagnostic_fixture=True)
            result = audit_camera_sources(attempt, diagnostic_fixture=True)
            self.assertEqual(result["decoded_images"], 12)
            self.assertEqual(manifest["rows"][1]["frame"], 101)
            self.assertFalse(result["physical_acceptance"])
            with self.assertRaisesRegex(ValueError, "already used"):
                write_camera_sources(attempt, frames, diagnostic_fixture=True)
            with self.assertRaisesRegex(ValueError, "provenance"):
                audit_camera_sources(attempt)

    def test_900_frame_diagnostic_decodes_all_3600_original_images(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt = Path(directory) / "attempt"
            capture = TickCapture(attempt, GEOMETRY, CONTEXT)
            frames = []
            images = {name: png((camera * 40, 60, 80)) for camera, name in enumerate(CAMERAS)}
            for index in range(900):
                row = raw(index % 3)
                row["frame"] = 100 + index
                row["time_s"] = round(index * .05, 8)
                capture.append(row)
                frames.append({"frame": row["frame"], "time_s": row["time_s"],
                               "cameras": images})
            capture.close()
            construction = attempt.parent / "construction.json"
            construction.write_text('{"case":"nearest_view_response"}\n')
            opendrive = b"<OpenDRIVE>diagnostic map</OpenDRIVE>"
            site = attempt.parent / "reviewed-site.json"
            site.write_text(json.dumps({"review_status": "reviewed",
                                        "map_opendrive_sha256": hashlib.sha256(opendrive).hexdigest()}) + "\n")
            write_capture_identity(attempt,
                "testing__C158208__NRS-484B-257-1__motor_vehicle_driver__nearest_view_response",
                construction, site, opendrive, diagnostic_fixture=True)
            write_camera_sources(attempt, frames, diagnostic_fixture=True)
            result = audit_camera_sources(attempt, diagnostic_fixture=True)
            self.assertEqual(result["decoded_images"], 3600)
            self.assertEqual(result["frame_count"], 900)

    def test_rejects_missing_camera_and_frame_time_swap(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt = Path(directory)
            frames = fixture(attempt)
            frames[1]["cameras"].pop("driver_reference")
            with self.assertRaisesRegex(ValueError, "four original cameras"):
                write_camera_sources(attempt, frames, diagnostic_fixture=True)
            frames[1]["cameras"]["driver_reference"] = png((1, 2, 3))
            frames[1]["time_s"] = .15
            with self.assertRaisesRegex(ValueError, "frame/time"):
                write_camera_sources(attempt, frames, diagnostic_fixture=True)

    def test_rejects_modified_archive_and_manifest_row(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt = Path(directory)
            frames = fixture(attempt)
            write_camera_sources(attempt, frames, diagnostic_fixture=True)
            archive = attempt / "nearest-view-overview-original-png.zip"
            with archive.open("ab") as stream:
                stream.write(b"tampered")
            with self.assertRaisesRegex(ValueError, "archive hash"):
                audit_camera_sources(attempt, diagnostic_fixture=True)
        with tempfile.TemporaryDirectory() as directory:
            attempt = Path(directory)
            frames = fixture(attempt)
            write_camera_sources(attempt, frames, diagnostic_fixture=True)
            path = attempt / "nearest-view-camera-manifest.json"
            manifest = json.loads(path.read_text())
            manifest["rows"][1]["frame"] = 999
            path.write_text(json.dumps(manifest) + "\n")
            with self.assertRaisesRegex(ValueError, "camera row"):
                audit_camera_sources(attempt, diagnostic_fixture=True)

    def test_original_mode_requires_full_duration_and_profile_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt = Path(directory)
            frames = fixture(attempt)
            with self.assertRaisesRegex(ValueError, "provenance"):
                write_camera_sources(attempt, frames)


if __name__ == "__main__":
    unittest.main()
