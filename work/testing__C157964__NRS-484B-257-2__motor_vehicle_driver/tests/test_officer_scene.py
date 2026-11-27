"""Construction tests exercise actual adapter calls and cleanup."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from officer_scene import CASES, construct, validate_site


def site():
    out = {"cell_id": "C157964", "actor": "motor_vehicle_driver",
           "control": "police_officer", "signal_controls": False,
           "layout": "one_way_to_two_way_intersection", "maneuver": "straight",
           "officer_controls_traffic": True,
           "ego_route_xy": [[-15, 0], [0, 0], [15, 0]],
           "other_spawn_xy": [0, -15], "officer_spawn_xy": [4, -4],
           "intersection_entry_station_m": 0, "upstream_reference_station_m": -3,
           "other_vehicle_obligated_to_stop_or_yield": False}
    for key in ("jurisdiction", "intersection_geometry", "entrance_controls",
                "officer_location", "officer_directive_visibility", "other_obligation",
                "ego_route", "other_route", "camera_sightlines"):
        out[key + "_source_sha256"] = "a" * 64
    return out


class Adapter:
    def __init__(self):
        self.calls = []
        self.fail = False

    def spawn_vehicle(self, at, role):
        self.calls.append(("spawn_vehicle", tuple(at), role))
        return role

    def spawn_officer(self, at):
        self.calls.append(("spawn_officer", tuple(at)))
        return "officer"

    def set_ego_route(self, ego, route):
        self.calls.append(("set_ego_route", ego, tuple(map(tuple, route))))

    def set_other_phase(self, other, phase, station):
        self.calls.append(("set_other_phase", other, phase, station))
        if self.fail:
            raise ValueError("phase setup failed")

    def set_officer_directive(self, officer, directive):
        self.calls.append(("set_officer_directive", officer, directive))

    def destroy(self, actor):
        self.calls.append(("destroy", actor))


class OfficerSceneTest(unittest.TestCase):
    def test_all_cases_create_three_actors_and_exact_controls(self):
        for case in CASES:
            with self.subTest(case=case.suffix):
                adapter = Adapter()
                result = construct(adapter, site(), case)
                self.assertEqual(result["actors"], ("ego", "other", "officer"))
                self.assertIn(("set_other_phase", "other", case.other_phase,
                               case.other_station_m), adapter.calls)
                self.assertIn(("set_officer_directive", "officer",
                               case.officer_directive), adapter.calls)

    def test_missing_officer_governance_rejected(self):
        scene = site()
        scene["officer_controls_traffic"] = False
        with self.assertRaisesRegex(ValueError, "governance"):
            validate_site(scene)

    def test_failed_spawn_setup_restores_actors(self):
        adapter = Adapter()
        adapter.fail = True
        with self.assertRaisesRegex(ValueError, "phase setup failed"):
            construct(adapter, site(), CASES[0])
        self.assertEqual(adapter.calls[-3:], [("destroy", "officer"),
                                              ("destroy", "other"),
                                              ("destroy", "ego")])


if __name__ == "__main__":
    unittest.main()
