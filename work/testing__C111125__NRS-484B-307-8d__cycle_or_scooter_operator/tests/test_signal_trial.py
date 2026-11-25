import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("c111125_signal_trial", ROOT / "signal_trial.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class SignalTrialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.refs = {}
        for name in ("native_trace", "device_trace", "detector_trace", "geometry"):
            path = self.root / (name + ".json")
            path.write_text('{"source":"' + name + '"}\n')
            self.refs[name] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        self.site = {"cell_id": "C111125", "maneuver": "straight",
                     "device_kind": "official_traffic_control_device", "ego_blueprint_class": "bicycle",
                     "ego_blueprint_id": "vehicle.bicycle.test", "rider_model_id": "walker.rider.test",
                     "device_id": "signal.1", "detector_id": "loop.1",
                     "detector_controls_subject_signal": True, "approach_lane_id": 1,
                     "cross_lane_id": 2, "stop_boundary_station_m": 1.0,
                     "entry_station_m": 9.0,
                     }
        packets = {
            "map": {k: self.site[k] for k in ("cell_id", "approach_lane_id", "cross_lane_id", "stop_boundary_station_m", "entry_station_m")},
            "device": {k: self.site[k] for k in ("device_id", "device_kind", "detector_id")},
            "detector": {"detector_id": self.site["detector_id"], "controls_device_id": self.site["device_id"], "zone_lane_id": self.site["approach_lane_id"]},
            "blueprint": {k: self.site[k] for k in ("ego_blueprint_id", "ego_blueprint_class", "rider_model_id")},
        }
        for name, data in packets.items():
            path = self.root / (name + ".json")
            path.write_text(json.dumps(data, sort_keys=True) + "\n")
            self.refs[name] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            self.site[name + "_ref"] = self.refs[name]

    def frames(self, cycles=2, stop=True, detector_failure=True, conflict=False):
        # Each element is an original 20 Hz readback. Repetition keeps the
        # bicycle stationary before the stop boundary while two rotations run.
        phases = ["red"] + [v for _ in range(cycles) for v in ("green", "yellow", "red")]
        phases += ["red", "red"]
        frames = []
        for i, phase in enumerate(phases):
            station = 0.0 if i < len(phases) - 2 else (5.0 if i == len(phases) - 2 else 10.0)
            frames.append({"frame": i, "timestamp_s": i / 20,
                           "subject_signal": "red" if detector_failure else ("green" if i == len(phases) - 1 else "red"),
                           "cross_signal": phase, "detector_occupied": True,
                           "detector_output": False if detector_failure else True,
                           "ego_speed_mps": 0.0 if stop and station == 0 else 1.0,
                           "ego_station_m": station,
                           "directed_participant_conflict": conflict if station == 10 else False})
        return frames

    def packet(self, suffix, frames):
        streams = {
            "native_trace": {"frames": frames, "blueprint_class": "bicycle"},
            "device_trace": {"frames": [{"frame": f.get("frame"), "subject_signal": f.get("subject_signal"), "cross_signal": f.get("cross_signal")} for f in frames]},
            "detector_trace": {"frames": [{"frame": f.get("frame"), "occupied": f.get("detector_occupied"), "output": f.get("detector_output")} for f in frames]},
            "geometry": {"stop_boundary_station_m": 1.0, "entry_station_m": 9.0},
        }
        for name, data in streams.items():
            path = self.root / (name + ".json")
            path.write_text(json.dumps(data, sort_keys=True) + "\n")
            self.refs[name] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        return {"case_suffix": suffix, "blueprint_class": "bicycle",
                "device_sha256": self.refs["device"]["sha256"],
                "map_sha256": self.refs["map"]["sha256"], "frames": frames,
                **{k + "_ref": self.refs[k] for k in ("native_trace", "device_trace", "detector_trace", "geometry")}}

    def test_construct_all_cases_with_source_readback(self):
        for suffix in ("two_cycles_failed_detection", "one_cycle", "signal_changes", "no_prior_stop", "fails_to_yield"):
            with self.subTest(suffix=suffix):
                plan = mod.construct_plan(self.site, self.root, suffix)
                self.assertEqual(plan["blueprint_class"], "bicycle")
        self.site["detector_controls_subject_signal"] = False
        with self.assertRaisesRegex(mod.SourceError, "detector/device link"):
            mod.construct_plan(self.site, self.root, "one_cycle")

    def test_rejects_rehashed_but_unbound_site_packets(self):
        detector = self.root / "detector.json"
        content = json.loads(detector.read_text())
        content["controls_device_id"] = "another.signal"
        detector.write_text(json.dumps(content, sort_keys=True) + "\n")
        self.site["detector_ref"]["sha256"] = hashlib.sha256(detector.read_bytes()).hexdigest()
        with self.assertRaisesRegex(mod.SourceError, "causal link lacks original source binding"):
            mod.construct_plan(self.site, self.root, "two_cycles_failed_detection")

    def test_measure_original_cycles_and_reject_missing_readbacks(self):
        plan = mod.construct_plan(self.site, self.root, "two_cycles_failed_detection")
        packet = self.packet(plan["case_suffix"], self.frames())
        result = mod.measure_attempt(packet, self.root, plan)
        self.assertEqual(result["complete_device_cycles_before_entry"], 2)
        self.assertTrue(result["prior_stop_observed"])
        self.assertTrue(result["detector_failure_observed"])
        del packet["frames"][2]["detector_output"]
        with self.assertRaisesRegex(mod.SourceError, "original Native trace"):
            mod.measure_attempt(packet, self.root, plan)

    def test_reject_stale_source_and_discontinuous_frames(self):
        plan = mod.construct_plan(self.site, self.root, "two_cycles_failed_detection")
        packet = self.packet(plan["case_suffix"], self.frames())
        packet["frames"][1]["frame"] = 100
        packet = self.packet(plan["case_suffix"], packet["frames"])
        with self.assertRaisesRegex(mod.SourceError, "discontinuity"):
            mod.measure_attempt(packet, self.root, plan)
        packet["frames"][1]["frame"] = 1
        packet = self.packet(plan["case_suffix"], packet["frames"])
        (self.root / "device_trace.json").write_text("modified")
        with self.assertRaisesRegex(mod.SourceError, "hash mismatch"):
            mod.measure_attempt(packet, self.root, plan)

    def test_measure_negative_variants(self):
        for suffix, kwargs, expected in (
            ("one_cycle", {"cycles": 1}, (1, True, True, False)),
            ("signal_changes", {"detector_failure": False}, (2, True, False, False)),
            ("no_prior_stop", {"stop": False}, (2, False, True, False)),
            ("fails_to_yield", {"conflict": True}, (2, True, True, True)),
        ):
            with self.subTest(suffix=suffix):
                plan = mod.construct_plan(self.site, self.root, suffix)
                result = mod.measure_attempt(self.packet(suffix, self.frames(**kwargs)), self.root, plan)
                self.assertEqual((result["complete_device_cycles_before_entry"], result["prior_stop_observed"],
                                  result["detector_failure_observed"], result["conflict_at_entry"]), expected)

    def test_late_detector_occupancy_cannot_count_as_failed_detection(self):
        plan = mod.construct_plan(self.site, self.root, "two_cycles_failed_detection")
        frames = self.frames()
        for row in frames[:-3]:
            row["detector_occupied"] = False
        measured = mod.measure_attempt(self.packet(plan["case_suffix"], frames), self.root, plan)
        self.assertEqual(measured["complete_device_cycles_before_entry"], 2)
        self.assertTrue(measured["detector_occupancy_observed"])
        self.assertFalse(measured["detector_occupied_through_completed_cycles"])
        self.assertFalse(measured["detector_failure_observed"])
        self.assertEqual(measured["completed_cycle_window_frames"], [1, 6])

    def test_rejects_resealed_invalid_original_readbacks(self):
        plan = mod.construct_plan(self.site, self.root, "two_cycles_failed_detection")
        bad_values = (
            ("timestamp_s", float("nan"), "joined frames differ"),
            ("timestamp_s", float("inf"), "finite timestamps"),
            ("ego_speed_mps", -0.1, "invalid original bicycle motion"),
            ("ego_speed_mps", float("nan"), "joined frames differ"),
            ("ego_station_m", float("inf"), "invalid original bicycle motion"),
            ("detector_occupied", 1, "invalid original detector"),
            ("detector_output", None, "invalid original detector"),
            ("directed_participant_conflict", "false", "invalid original detector"),
            ("cross_signal", "flashing_red", "invalid original signal"),
        )
        for field, value, message in bad_values:
            with self.subTest(field=field, value=value):
                frames = self.frames()
                frames[2][field] = value
                packet = self.packet(plan["case_suffix"], frames)
                with self.assertRaisesRegex(mod.SourceError, message):
                    mod.measure_attempt(packet, self.root, plan)

    def test_native_spawn_readback_policy_and_cleanup(self):
        class Actor:
            id = 17
            type_id = "vehicle.bicycle.test"
            destroyed = False
            def destroy(self):
                self.destroyed = True
        class Blueprint:
            id = "vehicle.bicycle.test"
        class Library:
            def find(self, identifier):
                return Blueprint() if identifier == Blueprint.id else None
        class World:
            def __init__(self):
                self.actor = Actor()
            def get_blueprint_library(self):
                return Library()
            def try_spawn_actor(self, blueprint, transform):
                self.blueprint, self.transform = blueprint, transform
                return self.actor
        world = World()
        policy = lambda plan, site: {"detector_sha256": plan["detector_sha256"], "device_sha256": plan["device_sha256"]}
        actor, receipt = mod.spawn_case(world, self.site, self.root, "two_cycles_failed_detection", "native_transform", policy)
        self.assertEqual(actor.id, receipt["observed_actor_id"])
        self.assertEqual(world.transform, "native_transform")
        self.assertFalse(actor.destroyed)
        world = World()
        with self.assertRaisesRegex(mod.SourceError, "policy receipt"):
            mod.spawn_case(world, self.site, self.root, "two_cycles_failed_detection", "native_transform", lambda *_: {})
        self.assertTrue(world.actor.destroyed)

    def test_live_control_uses_observed_cycles_and_conflict(self):
        observed = {"subject_signal": "red", "cross_signal": "red", "detector_occupied": True,
                    "detector_output": False, "ego_station_m": 0.0,
                    "directed_participant_conflict": False, "complete_device_cycles": 1}
        base = mod.construct_plan(self.site, self.root, "two_cycles_failed_detection")
        self.assertEqual(mod.control_step(base, observed)["target"], "hold_before_boundary")
        observed["complete_device_cycles"] = 2
        self.assertEqual(mod.control_step(base, observed)["target"], "straight_route")
        observed["directed_participant_conflict"] = True
        self.assertEqual(mod.control_step(base, observed)["target"], "hold_before_boundary")
        nonyield = mod.construct_plan(self.site, self.root, "fails_to_yield")
        self.assertEqual(mod.control_step(nonyield, observed)["target"], "straight_route")
        observed["complete_device_cycles"] = 1
        nonstop = mod.construct_plan(self.site, self.root, "no_prior_stop")
        self.assertEqual(mod.control_step(nonstop, observed)["target"], "creep_before_boundary")


if __name__ == "__main__":
    unittest.main()
