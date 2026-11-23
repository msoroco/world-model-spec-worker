import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


builder = load("restricted_zone")
auditor = load("zone_audit")


class FakeWorld:
    def __init__(self):
        self.calls = []

    def load_map(self, *a):
        self.calls.append(("map", *a))

    def mark_zone(self, *a):
        self.calls.append(("zone", *a))

    def spawn_vehicle(self, *a):
        self.calls.append(("spawn", *a))
        return a[0]

    def spawn_pedestrian(self, *a):
        self.calls.append(("pedestrian", *a))
        return a[0]

    def set_route(self, *a):
        self.calls.append(("route", *a))

    def schedule(self, *a):
        self.calls.append(("schedule", *a))


class ZoneTests(unittest.TestCase):
    def plan(self, **changes):
        d = dict(case_id="case", map_id="native-map-pending", zone_start_m=10,
                 zone_end_m=30, subject_stop_m=16, entrant_start_m=0,
                 entrant_destination_m=23, entrant_departure_s=6,
                 subject_departure_s=24, passenger_exchange_start_s=8,
                 passenger_exchange_end_s=15)
        d.update(changes)
        return builder.ZonePlan(**d)

    def test_constructs_zone_both_vehicles_routes_and_exchange(self):
        world = FakeWorld()
        builder.construct(self.plan(), world)
        self.assertEqual(len([c for c in world.calls if c[0] == "spawn"]), 2)
        self.assertIn(("route", "restricted-purpose-entrant", 23), world.calls)
        self.assertIn(("pedestrian", "passenger", 16), world.calls)
        self.assertIn(("schedule", "passenger", "complete_boarding_or_alighting", 15), world.calls)
        self.assertIn(("schedule", "subject", "passenger_exchange_end", 15), world.calls)
        self.assertIn(("schedule", "restricted-purpose-entrant", "request_reserved_parking", 6), world.calls)
        self.assertIn(("zone", 10, 30, "reserved vehicle parking",
                       "authored zone context pending independent authority review"), world.calls)

    def test_rejects_bad_geometry_and_exchange(self):
        for kwargs in (dict(subject_stop_m=31), dict(entrant_start_m=11),
                       dict(entrant_destination_m=31), dict(subject_departure_s=14)):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                builder.construct(self.plan(**kwargs), FakeWorld())

    def sources(self, base, blocked=False):
        frame_path = base / "frames.jsonl"
        context_path = base / "context.json"
        seal_path = base / "seal.json"
        frames = []
        for i in range(900):
            frames.append(dict(frame=i, time_s=i / 20, subject_station_m=16,
                               subject_speed_mps=0, entrant_station_m=4 if i < 250 else 11,
                               entrant_speed_mps=2 if i < 250 else 0,
                               entrant_waiting=blocked and 250 <= i < 400,
                               passenger_exchange_active=160 <= i < 300,
                               passenger_station_m=16,
                               passenger_boarding_state="approaching" if i < 160 else "boarding" if i < 300 else "aboard",
                               entrant_access_blocked=blocked and 250 <= i < 400,
                               entrant_parking_task_active=True))
        frame_path.write_text("".join(json.dumps(f) + "\n" for f in frames))
        context = dict(case_id="case", zone_start_m=10, zone_end_m=30,
                       restricted_purpose="reserved parking", restricted_source="scene-recorded sign and authority packet",
                       effective_conditions="scene-recorded effective interval",
                       subject_vehicle_class_source="registration/inspection packet",
                       driver_identity_source="actor assignment packet",
                       entrant_parking_purpose_source="task packet",
                       prohibited_stopping_exclusions_review="source review packet")
        context_path.write_text(json.dumps(context))
        sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        seal_path.write_text(json.dumps(dict(case_id="case", frames_sha256=sha(frame_path),
                                             context_sha256=sha(context_path))))
        return frame_path, context_path, seal_path

    def test_source_bound_original_history_reports_physical_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.sources(Path(tmp), blocked=True)
            result = auditor.audit_original_frames(*paths, "case")
            self.assertEqual(result["frame_count"], 900)
            self.assertGreater(result["entrant_access_blocked_frames"], 0)
            self.assertEqual(result["legal_interference"], "unresolved_judgment")

    def test_rejects_tamper_or_missing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.sources(Path(tmp))
            paths[0].write_text(paths[0].read_text().replace('"frame": 0', '"frame": 9', 1))
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                auditor.audit_original_frames(*paths, "case")
            paths[2].unlink()
            with self.assertRaisesRegex(ValueError, "missing original"):
                auditor.audit_original_frames(*paths, "case")

    def test_rejects_incomplete_original_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.sources(Path(tmp))
            with self.assertRaisesRegex(ValueError, "incomplete"):
                auditor.audit_original_frames(*paths, "case", expected_frames=901)

    def test_independent_comparison_checks_fixed_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.sources(Path(tmp), blocked=True)
            left = auditor.audit_original_frames(*paths, "case")
            right = dict(left, case_id="other", entrant_waiting_frames=0)
            compared = auditor.compare_cases(left, right)
            self.assertEqual(compared["observed_difference"]["entrant_waiting_frames"], [150, 0])
            self.assertEqual(compared["legal_comparison"], "unresolved_judgment")
            right["fixed_context"] = dict(right["fixed_context"], restricted_purpose="taxi stand")
            with self.assertRaisesRegex(ValueError, "fixed zone"):
                auditor.compare_cases(left, right)
            right.pop("frames_sha256")
            with self.assertRaisesRegex(ValueError, "sealed original"):
                auditor.compare_cases(left, right)


if __name__ == "__main__":
    unittest.main()
