from pathlib import Path
import sys
from types import SimpleNamespace as N
import tempfile
import unittest


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from native_conditions import NativeConditionCapture, sample_native
from saved_conditions import measure


ROAD = '<OpenDRIVE><road id="42"><lanes><laneSection s="0"><left>' \
       '<lane id="1" type="driving"><width sOffset="0" a="4" b="0" c="0" d="0"/></lane>' \
       '</left><right><lane id="-1" type="driving">' \
       '<width sOffset="0" a="3.5" b="0" c="0" d="0"/></lane></right>' \
       '</laneSection></lanes></road></OpenDRIVE>'


class Actor:
    def __init__(self, actor_id, x, lane_id=-1):
        self.id = actor_id
        self.location = N(x=x, y=0, lane_id=lane_id)
        self.bounding_box = N(extent=N(x=2))

    def get_transform(self):
        return N(location=self.location, get_forward_vector=lambda: N(x=1, y=0))

    def get_velocity(self):
        return N(x=8, y=0, z=0)

    def get_physics_control(self):
        return N(wheels=[N(tire_friction=1.0), N(tire_friction=.8)])


class Map:
    def get_waypoint(self, location, project_to_road=False):
        return N(road_id=42, lane_id=location.lane_id, s=10, lane_width=3.5, is_junction=False)

    def to_opendrive(self):
        return ROAD


class World:
    def get_map(self):
        return Map()

    def get_weather(self):
        return N(wetness=20, precipitation=30, fog_density=10)


class NativeConditionsTests(unittest.TestCase):
    def setUp(self):
        self.world = World()
        self.ego = Actor(1, 0)
        self.leader = Actor(2, 30)
        self.snapshot = N(frame=400, timestamp=N(elapsed_seconds=20.0))

    def test_original_native_readback_and_full_road_width(self):
        row = sample_native(self.world, self.ego, self.leader, self.snapshot)
        self.assertEqual(row["leader_gap_m"], 26)
        self.assertEqual(row["highway_width_m"], 7.5)
        self.assertEqual(row["roadway_driving_width_m"], 7.5)
        self.assertEqual(row["shoulder_width_m"], 0)
        self.assertEqual(row["surface_wetness"], .2)
        self.assertEqual(row["tire_friction"], .8)
        self.assertEqual(len(row["source_ids"]["opendrive_sha256"]), 64)

    def test_shoulder_kept_separate_from_driving_width(self):
        class ShoulderMap(Map):
            def to_opendrive(self):
                return ROAD.replace('</right>',
                    '<lane id="-2" type="shoulder"><width sOffset="0" a="1.25"/></lane></right>')
        self.world.get_map = lambda: ShoulderMap()
        row = sample_native(self.world, self.ego, self.leader, self.snapshot)
        self.assertEqual(row["roadway_driving_width_m"], 7.5)
        self.assertEqual(row["shoulder_width_m"], 1.25)
        self.assertEqual(row["highway_width_m"], 8.75)
        self.assertIn("boundary unverified", row["mapped_width_scope"])

    def test_wrong_lane_or_rear_actor_rejected(self):
        self.leader.location.lane_id = 1
        with self.assertRaisesRegex(ValueError, "ego's original roadway lane"):
            sample_native(self.world, self.ego, self.leader, self.snapshot)
        self.leader.location.lane_id = -1
        self.leader.location.x = -10
        with self.assertRaisesRegex(ValueError, "not ahead"):
            sample_native(self.world, self.ego, self.leader, self.snapshot)

    def test_missing_open_drive_width_rejected(self):
        class BadMap(Map):
            def to_opendrive(self):
                return ROAD.replace('type="driving"', 'type="shoulder"')
        self.world.get_map = lambda: BadMap()
        with self.assertRaisesRegex(ValueError, "no driving width"):
            sample_native(self.world, self.ego, self.leader, self.snapshot)

    def test_native_capture_seals_once_and_saved_measurement_rechecks(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = NativeConditionCapture(Path(directory), "exact-case")
            for index in range(3):
                capture.append(self.world, self.ego, self.leader,
                               N(frame=400 + index, timestamp=N(elapsed_seconds=20 + index * .05)))
            capture.close()
            self.assertEqual(measure(Path(directory), "exact-case")["provenance_kind"], "native_api_capture")
            with self.assertRaisesRegex(ValueError, "already closed"):
                capture.close()

    def test_native_capture_rejects_gap_before_seal(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = NativeConditionCapture(Path(directory), "exact-case")
            capture.append(self.world, self.ego, self.leader, self.snapshot)
            with self.assertRaisesRegex(ValueError, "contiguous at 20 Hz"):
                capture.append(self.world, self.ego, self.leader,
                               N(frame=402, timestamp=N(elapsed_seconds=20.1)))
            self.assertFalse((Path(directory) / "original-conditions-seal.json").exists())


if __name__ == "__main__":
    unittest.main()
