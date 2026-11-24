import hashlib
from io import BytesIO
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_attempt import run_native_attempt

ASSIGNMENT = "testing__C158208__NRS-484B-257-1__motor_vehicle_driver"
GEOMETRY = {"ego_route_origin_xy_m": [-10, 5], "ego_route_axis_xy": [1, 0],
            "through_route_origin_xy_m": [5, -10], "through_route_axis_xy": [0, 1],
            "ego_entry_station_m": 10,
            "intersection_polygon_xy_m": [[0, 0], [10, 0], [10, 10], [0, 10]]}
CONTEXT = {name: True for name in (
    "yield_sign_governs_approach", "no_marked_stop_line", "no_near_side_crosswalk",
    "no_sidewalk_derived_crosswalk", "through_highway_confirmed", "no_officer_control",
    "no_signal_control", "viewpoint_reviewed")}


def body(x, y):
    return [[x - 1, y - .5], [x + 1, y - .5],
            [x + 1, y + .5], [x - 1, y + .5]]


def png():
    stream = BytesIO()
    Image.new("RGB", (8, 6), "blue").save(stream, format="PNG")
    return stream.getvalue()


class World:
    def __init__(self):
        self.index = -1

    def get_map(self):
        return self

    def to_opendrive(self):
        return "<OpenDRIVE>site</OpenDRIVE>"

    def tick(self):
        self.index += 1
        return 100 + self.index

    def get_snapshot(self):
        return type("Snapshot", (), {"frame": 100 + self.index,
            "timestamp": type("Time", (), {"elapsed_seconds": self.index * .05})()})()


class Client:
    def __init__(self):
        self.world = World()

    def get_world(self):
        return self.world


class Restore:
    def __init__(self):
        self.calls = []
        self.fail = False

    def snapshot(self, client):
        self.calls.append("snapshot")
        return {"original": True}

    def restore(self, client, saved):
        self.calls.append("restore")
        if self.fail:
            raise ValueError("wrong restored map")
        return {"restored": True}


class Adapter:
    def __init__(self):
        self.destroyed = []
        self.commands = []
        self.fail_frame = None

    def configure(self, world, site):
        pass

    def spawn(self, world, site):
        return ["sign", "ego", "through"]

    def observe(self, world, actors, frame):
        i = world.index
        x = (-9, -5, 0)[i]
        y = (-8, -3, 4)[i]
        raw = {"frame": frame if i != self.fail_frame else frame + 1,
               "time_s": i * .05,
               "ego": {"body_vertices_xy_m": body(x, 5), "velocity_xy_mps": [3-i, 0]},
               "through_vehicle": {"center_xy_m": [5, y],
                                   "body_vertices_xy_m": body(5, y)},
               "visibility_probe": {"source": "native_raycast", "occluded": i == 0,
                                    "origin_xy_m": [x, 5], "target_xy_m": [5, y]},
               "sign_present": True}
        return {"raw_tick": raw,
                "cameras": {name: png() for name in (
                    "overview", "approach", "reference_corner", "driver_reference")}}

    def apply_control(self, actors, command):
        self.commands.append(command)

    def destroy(self, actor):
        self.destroyed.append(actor)


class NativeAttemptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.site = self.root / "site.json"
        self.site.write_text(json.dumps({"review_status": "reviewed", "cell_id": "C158208",
            "diagnostic_fixture": True, "capture_geometry": GEOMETRY,
            "ego_view_station_m": 8.0,
            "reviewed_context": CONTEXT,
            "map_opendrive_sha256": hashlib.sha256(b"<OpenDRIVE>site</OpenDRIVE>").hexdigest()}) + "\n")
        self.construction = self.root / "construction.json"
        self.construction.write_text('{"case": "response"}\n')
        self.client, self.adapter, self.restore = Client(), Adapter(), Restore()
        self.case = ASSIGNMENT + "__nearest_view_response"
        self.attempt = self.root / "attempt"

    def run_attempt(self):
        return run_native_attempt(self.client, self.adapter, self.restore,
            case_id=self.case, construction=self.construction,
            reviewed_site_packet=self.site, attempt=self.attempt,
            diagnostic_fixture=True)

    def test_original_timeline_bound_to_camera_and_owner_release(self):
        result = self.run_attempt()
        self.assertEqual(result["frame_count"], 3)
        self.assertEqual(result["camera_audit"]["decoded_images"], 12)
        self.assertEqual(result["source_kind"], "synthetic_fixture")
        self.assertEqual(self.adapter.commands[-1]["engineering_state"], "yield_hold")
        self.assertEqual(self.adapter.destroyed, ["through", "ego", "sign"])
        self.assertEqual(self.restore.calls, ["snapshot", "restore"])
        self.assertEqual(json.loads((self.attempt / "native-owner-release.json").read_text()), result)

    def test_stale_observation_rejects_receipt_but_restores(self):
        self.adapter.fail_frame = 1
        with self.assertRaisesRegex(ValueError, "world snapshot"):
            self.run_attempt()
        self.assertEqual(self.adapter.destroyed, ["through", "ego", "sign"])
        self.assertEqual(self.restore.calls, ["snapshot", "restore"])
        self.assertFalse((self.attempt / "native-owner-release.json").exists())

    def test_restore_failure_blocks_release(self):
        self.restore.fail = True
        with self.assertRaisesRegex(RuntimeError, "world restore"):
            self.run_attempt()
        self.assertFalse((self.attempt / "native-owner-release.json").exists())

    def test_wrong_map_refused_before_actor_mutation(self):
        self.site.write_text(self.site.read_text().replace("reviewed", "pending"))
        with self.assertRaisesRegex(ValueError, "reviewed C158208"):
            self.run_attempt()
        self.assertEqual(self.restore.calls, [])
        self.assertEqual(self.adapter.destroyed, [])


if __name__ == "__main__":
    unittest.main()
