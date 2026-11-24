import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from access_measurement import ASSIGNMENT
from native_capture import capture
from delivery_audit import audit
from alley_construction import build_plan
from parking_controller import ParkingController


class FakeAdapter:
    native_attested = False

    def __init__(self, kind="driveway", x=1, missing_camera=False, map_change=False):
        self.kind, self.x = kind, x
        self.missing_camera, self.map_change = missing_camera, map_change
        self.map_bytes = b"<OpenDRIVE><road id='alley-1'/></OpenDRIVE>"
        self.index = 0
        self.cleaned = False
        self.braked = False
        buffer = io.BytesIO()
        Image.new("RGB", (2, 2), (40, 50, 60)).save(buffer, format="PNG")
        self.png = buffer.getvalue()

    def get_map_packet(self, case):
        return {"case_id": case, "source_kind": "original_native_geometry",
                "map_sha256": hashlib.sha256(self.map_bytes).hexdigest(),
                "highway_status": True, "cul_de_sac": False,
                "highway_source": "survey:connected-public-highway",
                "alley_classification_source": "survey:alley-definition",
                "cul_de_sac_source": "survey:through-end",
                "property_abutting_source": "survey:parcel-boundary", "property_id": "parcel-1",
                "driveway_ownership_source": "survey:parcel-access",
                "vehicular_use_source": "survey:vehicle-entry",
                "ego_vehicle_id": "ego", "access_kind": self.kind,
                "centerline_start_m": [-50, 2], "centerline_end_m": [100, 2],
                "start_connection_source": "survey:through-connection-west",
                "end_connection_source": "survey:through-connection-east",
                "ego_length_m": 4.5, "ego_width_m": 1.8,
                "access_corridor_polygon_m": [[0, 0], [4, 0], [4, 5], [0, 5]]}

    def get_opendrive_bytes(self):
        if self.map_change and self.index >= 900:
            return self.map_bytes + b"changed"
        return self.map_bytes

    def start(self, plan):
        self.plan = plan

    def tick(self):
        i = self.index
        self.index += 1
        return {"frame": i + 1000, "time_s": round(i * .05, 2)}

    def read_footprint(self, frame):
        i = frame - 1000
        x = self.x
        return {"frame": frame, "time_s": round(i * .05, 2), "vehicle_id": "ego",
                "polygon_m": [[x, 1], [x + 2, 1], [x + 2, 3], [x, 3]]}

    def read_activity(self, frame):
        i = frame - 1000
        return {"frame": frame, "time_s": round(i * .05, 2),
                "state": "parked" if i >= 100 else "approaching",
                "speed_mps": 0 if i >= 100 else 2}

    def read_cameras(self, frame):
        row = {"frame": frame, "time_s": round((frame - 1000) * .05, 2),
               "png": self.png}
        return {name: row for name in (("overview", "approach", "reference_corner") if self.missing_camera
                                        else ("overview", "approach", "reference_corner", "driver_reference"))}

    def brake(self):
        self.braked = True

    def cleanup(self):
        self.cleaned = True


class CaptureTests(unittest.TestCase):
    def test_both_access_kinds_and_positions(self):
        for kind in ("driveway", "entrance"):
            for position, x, expected in (("overlap", 1, 4), ("clear", 5, 0)):
                with self.subTest(kind=kind, position=position), tempfile.TemporaryDirectory() as directory:
                    case = ASSIGNMENT + "__" + kind + "_" + position
                    adapter = FakeAdapter(kind, x)
                    output = Path(directory) / "attempt"
                    summary = capture(adapter, case, output)
                    self.assertEqual(summary["max_access_intrusion_area_m2"], expected)
                    self.assertEqual(summary["frame_count"], 900)
                    self.assertTrue(summary["diagnostic_fixture"])
                    self.assertEqual(summary["legal_blocking_judgment"], "unresolved")
                    self.assertTrue(adapter.braked and adapter.cleaned)
                    self.assertEqual(adapter.plan["case_id"], case)
                    self.assertEqual(adapter.plan["capture"]["rate_hz"], 20)
                    inventory = json.loads((output / "inventory.json").read_text())
                    self.assertEqual(set(inventory["media"]),
                                     {"overview", "approach", "reference_corner", "driver_reference"})
                    self.assertEqual(hashlib.sha256((output / "road.xodr").read_bytes()).hexdigest(),
                                     inventory["map_sha256"])
                    saved = audit(output, case, require_original=False)
                    self.assertEqual(saved["frame_count"], 900)
                    self.assertFalse(saved["physical_completion"])
                    with self.assertRaisesRegex(ValueError, "diagnostic fixture"):
                        audit(output, case)

    def test_saved_audit_rejects_mutated_camera_and_map(self):
        with tempfile.TemporaryDirectory() as directory:
            case = ASSIGNMENT + "__driveway_overlap"
            output = Path(directory) / "attempt"
            capture(FakeAdapter(), case, output)
            camera = output / "overview.zip"
            camera.write_bytes(camera.read_bytes() + b"mutation")
            with self.assertRaisesRegex(ValueError, "camera archive changed"):
                audit(output, case, require_original=False)
            capture_output = Path(directory) / "second"
            capture(FakeAdapter(), case, capture_output)
            (capture_output / "road.xodr").write_bytes(b"different map")
            with self.assertRaisesRegex(ValueError, "map hash changed"):
                audit(capture_output, case, require_original=False)

    def test_rejects_missing_camera_and_map_mutation(self):
        for adapter, expected in ((FakeAdapter(missing_camera=True), "four original"),
                                  (FakeAdapter(map_change=True), "map changed")):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(ValueError, expected):
                    capture(adapter, ASSIGNMENT + "__driveway_overlap", Path(directory) / "attempt")
                self.assertFalse((Path(directory) / "attempt").exists())
                self.assertTrue(adapter.braked and adapter.cleaned)

    def test_rejects_wrong_case_and_access_kind(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "unknown exact"):
                capture(FakeAdapter(), ASSIGNMENT + "__other", Path(directory) / "attempt")
            with self.assertRaisesRegex(ValueError, "access kind differs"):
                capture(FakeAdapter(kind="entrance"), ASSIGNMENT + "__driveway_clear",
                        Path(directory) / "attempt")

    def test_target_geometry_both_approach_directions(self):
        packet = FakeAdapter().get_map_packet(ASSIGNMENT + "__driveway_clear")
        for direction in (-1, 1):
            clear = build_plan(packet, ASSIGNMENT + "__driveway_clear", direction=direction)
            overlap = build_plan(packet, ASSIGNMENT + "__driveway_overlap", direction=direction)
            self.assertEqual(clear["planned_access_intrusion_area_m2"], 0)
            self.assertGreater(overlap["planned_access_intrusion_area_m2"], 0)
            self.assertEqual(clear["controller"], overlap["controller"])
            self.assertEqual(clear["capture"], overlap["capture"])
            self.assertNotEqual(clear["target_xy_m"], overlap["target_xy_m"])
        packet.pop("end_connection_source")
        with self.assertRaisesRegex(ValueError, "endpoint evidence missing"):
            build_plan(packet, ASSIGNMENT + "__driveway_overlap")

    def test_controller_requires_real_stop_and_hold_before_departure(self):
        for direction in (-1, 1):
            packet = FakeAdapter().get_map_packet(ASSIGNMENT + "__driveway_clear")
            plan = build_plan(packet, ASSIGNMENT + "__driveway_clear", direction=direction)
            controller = ParkingController(plan)
            yaw = 0 if direction == 1 else 3.141592653589793
            request = controller.step(xy_m=plan["start_xy_m"], yaw_rad=yaw,
                                      speed_mps=2, time_s=0)
            self.assertEqual(request["phase"], "approach")
            self.assertGreater(request["throttle"], 0)
            request = controller.step(xy_m=plan["target_xy_m"], yaw_rad=yaw,
                                      speed_mps=1, time_s=8)
            self.assertEqual(request["phase"], "braking")
            self.assertEqual(request["brake"], 1)
            request = controller.step(xy_m=plan["target_xy_m"], yaw_rad=yaw,
                                      speed_mps=0, time_s=9)
            self.assertEqual(request["phase"], "hold")
            request = controller.step(xy_m=plan["target_xy_m"], yaw_rad=yaw,
                                      speed_mps=0, time_s=28)
            self.assertEqual(request["phase"], "hold")
            request = controller.step(xy_m=plan["target_xy_m"], yaw_rad=yaw,
                                      speed_mps=0, time_s=29)
            self.assertEqual(request["phase"], "depart")
            self.assertGreater(request["throttle"], 0)
            request = controller.step(xy_m=plan["depart_xy_m"], yaw_rad=yaw,
                                      speed_mps=0, time_s=36)
            self.assertEqual(request["phase"], "done")
        with self.assertRaisesRegex(ValueError, "left surveyed alley"):
            controller.step(xy_m=[999, 999], yaw_rad=0, speed_mps=1, time_s=37)


if __name__ == "__main__":
    unittest.main()
