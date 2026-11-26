"""CPU fixture for Native source joins; synthetic bytes are never physical proof."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_capture
import door_measurement


class Settings:
    synchronous_mode = False
    fixed_delta_seconds = None


class Snapshot:
    def __init__(self, frame):
        self.frame = frame
        self.timestamp = type("Time", (), {"elapsed_seconds": frame * .05})()


class World:
    def __init__(self):
        self.settings = Settings()
        self.frame = 0
    def get_settings(self):
        return copy.copy(self.settings)
    def apply_settings(self, settings):
        self.settings = copy.copy(settings)
    def tick(self):
        self.frame += 1
        return self.frame
    def get_snapshot(self):
        return Snapshot(self.frame)


class Actor:
    def __init__(self, identity):
        self.id = identity
        self.is_alive = True
        self.destroyed = False
    def destroy(self):
        self.destroyed = True


class NativeCaptureTests(unittest.TestCase):
    def survey(self):
        return {"source_kind": "reviewed_original_native_site", "cell_id": "C135087",
                "layout": "narrow_road", "maneuver": "load_unload", "map_sha256": hashlib.sha256(b"map").hexdigest(),
                "loading_position_supported": True, "road_width_m": 9.0,
                "selected_vehicle_width_m": 2.0, "selected_vehicle_length_m": 4.0,
                "selected_vehicle_center_xy_m": [0.0, -2.0], "selected_vehicle_heading_deg": 0,
                "passing_start_xy_m": [-20.0, 2.0], "passing_end_xy_m": [25.0, 2.0],
                "loading_position_source_sha256": "a" * 64,
                "passing_route_source_sha256": "b" * 64,
                "selected_vehicle_blueprint": "vehicle.test.selected",
                "passing_vehicle_blueprint": "vehicle.test.passing",
                "cargo_actor_blueprint": "static.prop.test",
                "passenger_actor_blueprint": "walker.pedestrian.test"}

    def run_fixture(self, *, omit_articulation=False):
        case = native_capture.ASSIGNMENT + "__cargo_inactive"
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            survey = folder / "site.json"
            raw = (json.dumps(self.survey(), sort_keys=True) + "\n").encode()
            survey.write_bytes(raw)
            actors = {}
            world = World()
            def factory(_world, role, _packet, _variant):
                actor = Actor(len(actors) + 1)
                actors[role] = actor
                return actor
            door_state = {"open": False, "side": "left"}
            def door(_selected, action, side):
                door_state["open"] = action == "open"
                door_state["side"] = side
                return True
            loading_state = {"active": False}
            def loading(_actor, _selected, _kind, active, _index):
                loading_state["active"] = active
                return True
            def observe(frame, selected, passing, loading_actor):
                index = frame - 1
                x = -20 + index * .05
                return {"source_frame_id": frame,
                        "selected_vehicle_id": str(selected.id),
                        "passing_vehicle_id": str(passing.id),
                        "loading_actor_id": str(loading_actor.id),
                        "selected_vehicle_center_xy_m": [0.0, -2.0],
                        "selected_vehicle_heading_deg": 0,
                        "door_side": door_state["side"],
                        "door_angle_deg": 0 if omit_articulation else (70 if door_state["open"] else 0),
                        "door_observation_source": "native_articulation_readback",
                        "loading_actor_body_xy_m": [[0, 0], [1, 0], [1, 1], [0, 1]],
                        "loading_actor_speed_mps": .2 if loading_state["active"] else 0,
                        "loading_contact_with_vehicle": loading_state["active"],
                        "loading_observation_source": "native_actor_body_motion",
                        "passing_vehicle_center_xy_m": [x, 2.0],
                        "passing_vehicle_width_m": 2.0, "passing_vehicle_length_m": 4.0,
                        "passing_vehicle_body_xy_m": [[x-2, 1], [x+2, 1], [x+2, 3], [x-2, 3]]}
            def cameras(_world, _selected, names, _packet):
                return {name: lambda _frame: b"fixture-only" for name in names}
            args = dict(case_id=case, survey_path=survey,
                        survey_sha256=hashlib.sha256(raw).hexdigest(),
                        output=folder / "attempt", map_reader=lambda _world: b"map",
                        actor_factory=factory, door_controller=door,
                        loading_controller=loading, original_observer=observe,
                        camera_factory=cameras)
            if omit_articulation:
                with self.assertRaisesRegex(ValueError, "did not open"):
                    native_capture.capture(world, **args)
            else:
                inventory = native_capture.capture(world, **args)
                result = door_measurement.measure(folder / "attempt", inventory, case,
                                                  Path(native_capture.__file__).parent / "case-plan.json")
                self.assertEqual(result["inactive_open_duration_s"], 18.0)
                self.assertTrue(result["door_closest_to_passing_traffic"])
                self.assertEqual(result["legal_necessity_or_immediacy"], "unresolved")
            self.assertFalse(world.get_settings().synchronous_mode)
            self.assertTrue(all(actor.destroyed for actor in actors.values()))

    def test_original_packet_roundtrip_and_restoration(self):
        self.run_fixture()

    def test_command_without_articulation_fails_closed(self):
        self.run_fixture(omit_articulation=True)

    def test_reviewed_survey_requires_original_route(self):
        survey = self.survey()
        survey["passing_end_xy_m"] = [25.0, -2.0]
        with self.assertRaisesRegex(ValueError, "crosses"):
            native_capture.validate_survey(survey, native_capture.ASSIGNMENT + "__cargo_active")


if __name__ == "__main__":
    unittest.main()
