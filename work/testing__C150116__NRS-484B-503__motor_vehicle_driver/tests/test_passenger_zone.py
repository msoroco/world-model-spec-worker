import copy
import importlib.util
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "passenger_zone.py"
spec = importlib.util.spec_from_file_location("passenger_zone", MODULE)
zone = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = zone
spec.loader.exec_module(zone)


def site(effective=True):
    return {"cell_id": "C150116", "layout": "one_way_road",
            "road": {"source_sha256": "road", "one_way_readback": True, "approach_waypoints": [[-10, 1], [1, 1]]},
            "zone": {"marking_source_sha256": "mark", "boundary_source_sha256": "boundary",
                     "designation": "passenger_curb_loading", "curb_adjacency_source_sha256": "curb",
                     "polygon_xy": [[0, 0], [10, 0], [10, 2], [0, 2]],
                     "parking_pose": [4, 1], "parking_pose_source_sha256": "pose", "passenger_anchor": [5, 2]},
            "clock": {"civil_time_iso": "2026-11-23T12:00:00-08:00", "timezone": "America/Los_Angeles", "source_sha256": "clock"},
            "regulations": {"source_sha256": "reg", "jurisdiction": "Nevada municipality source pending",
                            "effective_hours_source_sha256": "hours", "effective_at_civil_time": effective},
            "vehicle_blueprint": "vehicle.test", "vehicle_blueprint_source_sha256": "vehicle",
            "passenger_blueprint": "walker.test", "passenger_blueprint_source_sha256": "passenger"}


class Adapter:
    def __init__(self, fail_passenger=False):
        self.calls = []
        self.fail_passenger = fail_passenger

    def spawn_vehicle(self, *args, **kwargs):
        self.calls.append(("vehicle", args, kwargs))
        return "ego"

    def spawn_passenger(self, *args, **kwargs):
        self.calls.append(("passenger", args, kwargs))
        return None if self.fail_passenger else "passenger"

    def set_route(self, *args):
        self.calls.append(("route", args, {}))

    def set_conduct(self, *args):
        self.calls.append(("conduct", args, {}))

    def set_passenger_action(self, *args, **kwargs):
        self.calls.append(("action", args, kwargs))

    def destroy(self, actor):
        self.calls.append(("destroy", (actor,), {}))


def rows(case, event_frame=300):
    out = []
    for i in range(900):
        out.append({"case_id": case.name, "original_frame": 1000 + i, "elapsed_s": i / 20,
                    "ego_id": "ego", "passenger_id": "passenger", "map_sha256": "road",
                    "zone_source_sha256": "boundary", "regulations_source_sha256": "reg",
                    "clock_source_sha256": "clock", "source_sha256": "packet", "control_source_sha256": "control",
                    "ego_center_xy": [4, 1], "ego_speed_mps": 0,
                    "passenger_event": "boarding_started" if i == event_frame else None,
                    "passenger_event_source_sha256": "event" if i == event_frame else None})
    return out


class PassengerZoneTests(unittest.TestCase):
    def test_all_cases_construct_distinct_control_paths(self):
        for case in zone.CASES[:7]:
            adapter = Adapter()
            result = zone.build_case(adapter, site(case.hours == "effective"), case)
            self.assertEqual(result["case"], case.name)
            self.assertEqual([x[0] for x in adapter.calls], ["vehicle", "passenger", "route", "conduct", "action"])
            self.assertEqual(adapter.calls[-1][2]["release_delay_s"], case.release_delay_s)

    def test_sweep_sources_rejected_before_native_spawn(self):
        for case in (zone.CASES[7], zone.CASES[10], zone.CASES[13]):
            adapter = Adapter()
            with self.assertRaises(ValueError):
                zone.build_case(adapter, site(case.hours == "effective"), case)
            self.assertFalse(adapter.calls)

    def test_original_survey_offset_and_clock_boundary_are_checked(self):
        marked = site()
        marked["zone"].update(parking_pose=[4, 2.5], boundary_offset_source_sha256="original-survey",
                              feasible_boundary_offsets_m=[-0.5, 0.5])
        zone.validate_site(marked, zone.CASES[7])
        marked["zone"]["parking_pose"] = [4, 1]
        with self.assertRaisesRegex(ValueError, "surveyed parking pose differs"):
            zone.validate_site(marked, zone.CASES[7])
        clocked = site(False)
        clocked["clock"].update(effective_boundary_civil_iso="2026-11-23T12:30:00-08:00",
                                effective_boundary_source_sha256="original-regulation")
        zone.validate_site(clocked, zone.CASES[10])
        clocked["clock"]["effective_boundary_civil_iso"] = "2026-11-23T13:00:00-08:00"
        with self.assertRaisesRegex(ValueError, "sourced civil clock differs"):
            zone.validate_site(clocked, zone.CASES[10])

    def test_bad_site_and_hours_rejected_before_spawn(self):
        for mutation in (lambda s: s["road"].update(one_way_readback=False),
                         lambda s: s["zone"].update(designation="generic_loading"),
                         lambda s: s["regulations"].update(effective_at_civil_time=False),
                         lambda s: s["zone"].update(boundary_source_sha256="")):
            s = site()
            mutation(s)
            adapter = Adapter()
            with self.assertRaises(ValueError):
                zone.build_case(adapter, s, zone.CASES[0])
            self.assertFalse(adapter.calls)

    def test_spawn_failure_restores_owned_actor(self):
        adapter = Adapter(fail_passenger=True)
        with self.assertRaises(ValueError):
            zone.build_case(adapter, site(), zone.CASES[0])
        self.assertEqual(adapter.calls[-1][0], "destroy")

    def test_measure_original_events_and_zone(self):
        result = zone.measure_history(rows(zone.CASES[3]), zone.CASES[3], site())
        self.assertEqual(result["in_zone_halted_frame_count"], 900)
        self.assertEqual(result["passenger_events"][0]["frame"], 1300)
        self.assertIsNone(result["legal_judgment"])

    def test_measure_rejects_missing_event_source_and_actor_change(self):
        for change in (lambda r: r[300].update(passenger_event_source_sha256=""),
                       lambda r: r[400].update(passenger_id="other"),
                       lambda r: r[450].update(original_frame=1449)):
            data = rows(zone.CASES[3])
            change(data)
            with self.assertRaises(ValueError):
                zone.measure_history(data, zone.CASES[3], site())

    def test_pair_rejects_fixed_change(self):
        base = {"case_id": "a", "frame_count": 900, "original_history_sha256": "h1", "site_sha256": "s",
                "camera_plan_sha256": "camera", "zone_source_sha256": "zone", "vehicle_blueprint": "v",
                "passenger_blueprint": "p", "conduct": "park", "regulations_effective": True}
        other = dict(base, case_id="b", original_history_sha256="h2", conduct="stop")
        self.assertEqual(zone.audit_pair(base, other, "conduct")["difference"], "conduct")
        other["site_sha256"] = "changed"
        with self.assertRaises(ValueError):
            zone.audit_pair(base, other, "conduct")


if __name__ == "__main__":
    unittest.main()
