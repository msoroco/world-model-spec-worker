import io
import json
import pathlib
import sys
import tempfile
import unittest

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_acquisition import capture
from saved_left_turn import ASSIGNMENT_ID, process


def waypoint(x, y, junction):
    return {"x_m": x, "y_m": y, "road_id": 1, "lane_id": 1,
            "junction_id": junction, "source_ref": "diagnostic-map-waypoint"}


def body(x, y):
    return [[x + dx, y + dy, dz] for dz in (-0.5, 0.5)
            for dx in (-0.5, 0.5) for dy in (-0.5, 0.5)]


def png():
    stream = io.BytesIO()
    Image.new("RGB", (4, 4), (20, 30, 40)).save(stream, format="PNG")
    return stream.getvalue()


class Adapter:
    def __init__(self):
        self.next_frame = 100
        self.native_origin = False
        self.drop = False
        self.bad_png = False

    def source_attestation(self):
        return {"source_id": "test-original", "native_map_sha256": "a" * 64,
                "native_origin": self.native_origin}

    def tick(self):
        frame = self.next_frame
        self.next_frame += 2 if self.drop else 1
        sample = {"ego_vertices": body(0, 0), "opponent_vertices": body(1, 0),
                  "ego_actor_id": 11, "opponent_actor_id": 12,
                  "ego_driver_control_source": "fixture ego control callback",
                  "opponent_driver_control_source": "fixture opponent control callback",
                  "ego_heading": [1, 0], "opponent_heading": [-1, 0],
                  "ego_speed_mps": 1, "opponent_speed_mps": 5,
                  "ego_signal_left": True, "ego_turn_committed": False,
                  "opponent_cleared": False, "ego_braking": True}
        image = b"bad" if self.bad_png else png()
        return frame, frame / 20, sample, {name: image for name in ("overview", "approach", "reference_corner", "driver_reference")}


class NativeAcquisition(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.case = ASSIGNMENT_ID + "__inside_yield"
        self.packet = {"map_sha256": "a" * 64, "source_ref": "diagnostic-map",
                       "junction_id": 9, "intersection_polygon": [[-5, -5], [5, -5], [5, 5], [-5, 5]],
                       "ego_route": [waypoint(0, -10, None), waypoint(0, 0, 9), waypoint(-10, 0, None)],
                       "opposing_route": [waypoint(0, 10, None), waypoint(0, 0, 9), waypoint(0, -10, None)],
                       "ego_blueprint_id": "vehicle.ego", "opponent_blueprint_id": "vehicle.other"}
        self.map_path = self.root / "map.json"
        self.write_map()
        self.adapter = Adapter()

    def tearDown(self):
        self.tmp.cleanup()

    def write_map(self):
        self.map_path.write_text(json.dumps(self.packet) + "\n", encoding="utf-8")

    def run_capture(self):
        return capture(adapter=self.adapter, case_id=self.case, map_path=self.map_path,
                       output=self.root / "attempt", frame_count=2)

    def test_seals_original_actor_and_four_cameras_as_diagnostic(self):
        paths = self.run_capture()
        receipt = json.loads(paths["receipt_path"].read_text())
        self.assertTrue(receipt["diagnostic_fixture"])
        self.assertEqual(receipt["frame_count"], 2)
        self.assertEqual(len(list((self.root / "attempt" / "original-frames").iterdir())), 8)
        with self.assertRaisesRegex(ValueError, "diagnostic fixture"):
            process(case_id=self.case, map_path=paths["map_path"],
                    trace_path=paths["trace_path"], receipt_path=paths["receipt_path"])

    def test_attested_and_reviewed_source_joins_saved_path(self):
        self.adapter.native_origin = True
        self.packet["reviewed_original_map"] = True
        self.write_map()
        paths = self.run_capture()
        result = process(case_id=self.case, map_path=paths["map_path"],
                         trace_path=paths["trace_path"], receipt_path=paths["receipt_path"])
        self.assertEqual(len(result["frames"]), 2)
        self.assertEqual(result["physical_acceptance"], "unverified")

    def test_rejects_mutated_camera(self):
        self.adapter.native_origin = True
        self.packet["reviewed_original_map"] = True
        self.write_map()
        paths = self.run_capture()
        image = self.root / "attempt" / "original-frames" / "000000100-overview.png"
        image.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "sealed original camera bytes changed"):
            process(case_id=self.case, map_path=paths["map_path"],
                    trace_path=paths["trace_path"], receipt_path=paths["receipt_path"])

    def test_rejects_drop_and_bad_pixel_source(self):
        self.adapter.drop = True
        with self.assertRaisesRegex(ValueError, "dropped or duplicated"):
            self.run_capture()
        self.adapter = Adapter()
        self.adapter.bad_png = True
        with self.assertRaisesRegex(ValueError, "valid PNG"):
            capture(adapter=self.adapter, case_id=self.case, map_path=self.map_path,
                    output=self.root / "second-attempt", frame_count=2)

    def test_rejects_nonempty_attempt(self):
        attempt = self.root / "attempt"
        attempt.mkdir()
        (attempt / "occupied").write_text("x")
        with self.assertRaisesRegex(ValueError, "must be empty"):
            self.run_capture()


if __name__ == "__main__":
    unittest.main()
