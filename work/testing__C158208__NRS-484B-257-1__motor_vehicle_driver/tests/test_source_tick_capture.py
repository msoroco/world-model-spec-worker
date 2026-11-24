import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


capture = module("source_tick_capture")
measurement = module("nearest_view_measurement")


GEOMETRY = {"ego_route_origin_xy_m": [-10, 5], "ego_route_axis_xy": [1, 0],
            "through_route_origin_xy_m": [5, -10], "through_route_axis_xy": [0, 1],
            "ego_entry_station_m": 10,
            "intersection_polygon_xy_m": [[0, 0], [10, 0], [10, 10], [0, 10]]}
CONTEXT = {name: True for name in (
    "yield_sign_governs_approach", "no_marked_stop_line", "no_near_side_crosswalk",
    "no_sidewalk_derived_crosswalk", "through_highway_confirmed", "no_officer_control",
    "no_signal_control", "viewpoint_reviewed")}


def body(cx, cy):
    return [[cx - 1, cy - .5], [cx + 1, cy - .5],
            [cx + 1, cy + .5], [cx - 1, cy + .5]]


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


class SourceTickCaptureTests(unittest.TestCase):
    def test_identity_writer_binds_actual_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attempt = root / "attempt"
            writer = capture.TickCapture(attempt, GEOMETRY, CONTEXT)
            for index in range(3):
                writer.append(raw(index))
            writer.close()
            construction = root / "construction.json"
            construction.write_text('{"case":"exact"}\n')
            opendrive = b"<OpenDRIVE>test map</OpenDRIVE>"
            site = root / "site.json"
            site.write_text(json.dumps({"review_status": "reviewed",
                "map_opendrive_sha256": hashlib.sha256(opendrive).hexdigest()}) + "\n")
            case = "testing__C158208__NRS-484B-257-1__motor_vehicle_driver__nearest_view_response"
            result = capture.write_capture_identity(attempt, case, construction, site,
                                                    opendrive, diagnostic_fixture=True)
            self.assertEqual(result["case_id"], case)
            self.assertEqual(result["construction_sha256"], hashlib.sha256(construction.read_bytes()).hexdigest())
            self.assertEqual(result, json.loads((attempt / "capture-identity.json").read_text()))
            with self.assertRaisesRegex(ValueError, "already exists"):
                capture.write_capture_identity(attempt, case, construction, site,
                                               opendrive, diagnostic_fixture=True)

    def test_identity_writer_rejects_unreviewed_or_wrong_map(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attempt = root / "attempt"
            writer = capture.TickCapture(attempt, GEOMETRY, CONTEXT)
            for index in range(3):
                writer.append(raw(index))
            writer.close()
            construction = root / "construction.json"
            construction.write_text("{}\n")
            site = root / "site.json"
            site.write_text(json.dumps({"review_status": "pending",
                "map_opendrive_sha256": hashlib.sha256(b"map-a").hexdigest()}) + "\n")
            case = "testing__C158208__NRS-484B-257-1__motor_vehicle_driver__nearest_view_response"
            with self.assertRaisesRegex(ValueError, "reviewed site packet differs"):
                capture.write_capture_identity(attempt, case, construction, site, b"map-a",
                                               diagnostic_fixture=True)
            site.write_text(json.dumps({"review_status": "reviewed",
                "map_opendrive_sha256": hashlib.sha256(b"map-a").hexdigest()}) + "\n")
            with self.assertRaisesRegex(ValueError, "reviewed site packet differs"):
                capture.write_capture_identity(attempt, case, construction, site, b"map-b",
                                               diagnostic_fixture=True)
            with self.assertRaisesRegex(ValueError, "900 contiguous"):
                capture.write_capture_identity(attempt, case, construction, site, b"map-a")

    def test_sealed_originals_rederive_measured_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = capture.TickCapture(Path(directory), GEOMETRY, CONTEXT)
            for index in range(3):
                writer.append(raw(index))
            seal = writer.close()
            packet = capture.verify_seal(Path(directory))
            result = measurement.measure(packet)
            self.assertEqual(seal["frame_count"], 3)
            self.assertEqual(result["first_view"]["index"], 1)
            self.assertEqual(result["intersection_entry"]["index"], 2)
            self.assertEqual(result["minimum_approach_speed_mps"], 1)

    def test_rejects_missing_native_visibility_probe(self):
        value = raw(0)
        value["visibility_probe"]["source"] = "authored_boolean"
        with self.assertRaisesRegex(ValueError, "Native visibility probe"):
            capture.derive(value, GEOMETRY)

    def test_rejects_visibility_origin_on_another_vehicle(self):
        value = raw(0)
        value["visibility_probe"]["origin_xy_m"] = [5, -8]
        with self.assertRaisesRegex(ValueError, "ray origin differs"):
            capture.derive(value, GEOMETRY)

    def test_rejects_visibility_target_outside_through_body(self):
        value = raw(0)
        value["visibility_probe"]["target_xy_m"] = [50, 50]
        with self.assertRaisesRegex(ValueError, "ray target differs"):
            capture.derive(value, GEOMETRY)

    def test_rejects_through_center_outside_original_body(self):
        value = raw(0)
        value["through_vehicle"]["center_xy_m"] = [50, 50]
        with self.assertRaisesRegex(ValueError, "through center differs"):
            capture.derive(value, GEOMETRY)

    def test_rejects_noncontiguous_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = capture.TickCapture(Path(directory), GEOMETRY, CONTEXT)
            writer.append(raw(0))
            later = raw(1)
            later["frame"] = 102
            with self.assertRaisesRegex(ValueError, "frames must be contiguous"):
                writer.append(later)

    def test_rejects_changed_original_tick_after_seal(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = capture.TickCapture(Path(directory), GEOMETRY, CONTEXT)
            for index in range(3):
                writer.append(raw(index))
            writer.close()
            with writer.path.open("a") as stream:
                stream.write("{}\n")
            with self.assertRaisesRegex(ValueError, "original tick source hash differs"):
                capture.verify_seal(Path(directory))

    def test_rejects_reused_original_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = capture.TickCapture(Path(directory), GEOMETRY, CONTEXT)
            for index in range(3):
                writer.append(raw(index))
            writer.close()
            with self.assertRaisesRegex(ValueError, "already used"):
                capture.TickCapture(Path(directory), GEOMETRY, CONTEXT)

    def test_rejects_output_under_runtime_before_creating_it(self):
        with tempfile.TemporaryDirectory() as directory:
            forbidden = Path(directory) / "runtime" / "attempt"
            with self.assertRaisesRegex(ValueError, "frozen runtime"):
                capture.TickCapture(forbidden, GEOMETRY, CONTEXT)
            self.assertFalse(forbidden.exists())

    def test_rejects_degenerate_original_body(self):
        value = raw(0)
        value["through_vehicle"]["body_vertices_xy_m"] = [[5, 0], [5, 1], [5, 2], [5, 3]]
        with self.assertRaisesRegex(ValueError, "body polygons must be valid"):
            capture.derive(value, GEOMETRY)


if __name__ == "__main__":
    unittest.main()
