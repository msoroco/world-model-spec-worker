import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import native_capture
from test_median_opening import scene


class Map:
    def to_opendrive(self):
        return "inspected map"

    def get_waypoint(self, location, project_to_road=False):
        return SimpleNamespace(
            transform=SimpleNamespace(location=location),
            road_id=1 if location.y != 0 else 2,
            is_junction=location.x == 0 and location.y == 0)


class World:
    def get_map(self):
        return Map()


def packet(root):
    selected = scene()
    selected.update({
        "review_status": "reviewed_original", "reviewer": "diagnostic test reviewer",
        "cell_id": "C125697", "actor": "motor_vehicle_driver",
        "opposing_left_turn_excluded_source": "diagnostic route sample",
        "subsection_4_applicability_review": "pending independent legal applicability review",
        "cameras": {name: {"dimensions": list(native_capture.DIMENSIONS[name]),
                           "mount": "world",
                           "pose": {"x": 0, "y": 0, "z": 8, "pitch": -30, "yaw": 0, "roll": 0}}
                    for name in native_capture.CAMERAS},
    })
    selected["governing_signal"]["actor_id"] = 77
    sources = {
        "device_inventory": {"governing_signal_actor_id": 77,
                             "controlled_approach_road_ids": [1, 2]},
        "highway_identity": {"ego_highway": "north-south",
                             "other_highway": "east-west",
                             "public_access_confirmed": True},
    }
    refs = {}
    for name, body in sources.items():
        data = json.dumps(body).encode()
        (root / (name + ".json")).write_bytes(data)
        refs[name] = {"path": name + ".json", "sha256": hashlib.sha256(data).hexdigest(),
                      "citation": "synthetic test source"}
    selected["source_refs"] = refs
    path = root / "site.json"
    path.write_text(json.dumps(selected))
    return path


class NativeCaptureTests(unittest.TestCase):
    def test_reviewed_source_packet_and_negative_guards(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = packet(root)
            factory = lambda x, y: SimpleNamespace(x=x, y=y, z=0)
            value, sources = native_capture.reviewed_packet(path, World(), factory)
            self.assertEqual(value["governing_signal"]["actor_id"], 77)
            self.assertEqual(set(sources), {"opendrive", "device_inventory", "highway_identity"})
            (root / "device_inventory.json").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "source changed"):
                native_capture.reviewed_packet(path, World(), factory)
            packet(root)
            value = json.loads(path.read_text())
            value["cameras"]["overview"]["dimensions"] = [320, 180]
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "camera profile differs"):
                native_capture.reviewed_packet(path, World(), factory)
            value["cameras"]["overview"]["dimensions"] = list(native_capture.DIMENSIONS["overview"])
            value["subsection_4_applicability_review"] = ""
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "subsection 4"):
                native_capture.reviewed_packet(path, World(), factory)

    def test_selected_controller_applies_brake_or_route_control(self):
        controls = []
        carla = SimpleNamespace(VehicleControl=lambda **kwargs: SimpleNamespace(**kwargs))
        actor = SimpleNamespace(
            apply_control=controls.append,
            get_location=lambda: SimpleNamespace(x=0.0, y=-10.0),
            get_transform=lambda: SimpleNamespace(rotation=SimpleNamespace(yaw=90.0)),
            get_velocity=lambda: SimpleNamespace(x=0.0, y=0.0, z=0.0))
        route = [[0, -10], [0, 0], [0, 10]]
        self.assertEqual(native_capture._control(carla, actor, route, 1, "brake"), 1)
        self.assertEqual(controls[-1].brake, 1.0)
        self.assertEqual(native_capture._control(carla, actor, route, 1, "proceed"), 1)
        self.assertGreater(controls[-1].throttle, 0)
        actor.get_location = lambda: SimpleNamespace(x=0.0, y=9.0)
        self.assertEqual(native_capture._control(carla, actor, route, 2, "proceed"), 2)
        self.assertEqual(controls[-1].brake, 1.0)


if __name__ == "__main__":
    unittest.main()
