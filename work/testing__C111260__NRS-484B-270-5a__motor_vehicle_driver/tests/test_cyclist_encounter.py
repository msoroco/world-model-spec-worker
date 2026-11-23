import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cyclist_encounter", ROOT / "cyclist_encounter.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def waypoint(x, y, junction=None):
    return {"x_m": x, "y_m": y, "road_id": 1, "lane_id": 1,
            "junction_id": junction, "source_ref": "map.opendrive#waypoint"}


def site(kind="bicycle"):
    rider = {"source_ref": "blueprints.json#rider", "blueprint_id": "vehicle.bicycle",
             "person_actor_id": 42, "kind": kind, "moped": False, "motorized": False,
             "wheel_diameters_in": [26, 26], "electric_assist": kind == "electric_bicycle",
             "standing_platform": kind == "electric_scooter"}
    return {"map_sha256": "a" * 64, "map_source_ref": "map.opendrive", "junction_id": 7,
            "ego_route": [waypoint(-20, 0), waypoint(0, 0, 7), waypoint(20, 0)],
            "rider_route": [waypoint(0, -20), waypoint(0, 0, 7), waypoint(0, 20)],
            "motor_vehicle": {"source_ref": "blueprints.json#ego", "blueprint_id": "vehicle.sedan",
                              "rail_bound": False}, "rider": rider}


def history(kind="bicycle", brake=0.7):
    return [{"source": "original_native", "map_sha256": "a" * 64, "frame": n,
             "time_s": n * 0.05, "ego_actor_id": 1, "rider_actor_id": 2,
             "rider_kind_observed": kind, "rider_mounted_observed": True,
             "surface_gap_m": 3.0 - n * 0.2, "ego_speed_mps": 8.0,
             "rider_speed_mps": 3.0, "ego_brake_observed": brake,
             "conflict_window_observed": True, "contact_observed": False}
            for n in range(3)]


class SiteTests(unittest.TestCase):
    def test_native_spawn_and_cleanup(self):
        class Blueprint:
            def __init__(self, name):
                self.id = name

        class Library:
            def find(self, name):
                return Blueprint(name)

        class Actor:
            def __init__(self, name):
                self.type_id = name
                self.destroyed = False

            def destroy(self):
                self.destroyed = True

        class World:
            def __init__(self, fail_second=False):
                self.actors = []
                self.fail_second = fail_second

            def get_blueprint_library(self):
                return Library()

            def try_spawn_actor(self, blueprint, transform):
                if self.fail_second and self.actors:
                    return None
                actor = Actor(blueprint.id)
                self.actors.append(actor)
                return actor

        world = World()
        made = MODULE.spawn_encounter(world, site(), "bicycle", lambda position: position)
        self.assertEqual(made["blueprint_ids"], ("vehicle.sedan", "vehicle.bicycle"))
        self.assertEqual(len(world.actors), 2)
        world = World(fail_second=True)
        with self.assertRaisesRegex(ValueError, "spawn failed"):
            MODULE.spawn_encounter(world, site(), "bicycle", lambda position: position)
        self.assertTrue(world.actors[0].destroyed)

    def test_all_rider_alternatives(self):
        for kind in MODULE.RIDER_KINDS:
            with self.subTest(kind=kind):
                self.assertTrue(MODULE.validate_site(site(kind), kind)["crossing_conflict"])

    def test_missing_route_crossing(self):
        packet = site()
        packet["rider_route"] = [waypoint(0, 10), waypoint(0, 20, 7), waypoint(0, 30)]
        with self.assertRaisesRegex(ValueError, "no crossing"):
            MODULE.validate_site(packet, "bicycle")

    def test_bicycle_requires_observed_identity(self):
        packet = site()
        packet["rider"]["wheel_diameters_in"] = [12, 12]
        with self.assertRaisesRegex(ValueError, "tandem-wheel"):
            MODULE.validate_site(packet, "bicycle")
        packet = site()
        packet["rider"]["moped"] = True
        with self.assertRaisesRegex(ValueError, "classification"):
            MODULE.validate_site(packet, "bicycle")

    def test_response_pair(self):
        self.assertGreater(MODULE.control_step(8, 16, 2, "brake")["brake"], 0.5)
        self.assertEqual(MODULE.control_step(8, 16, 2, "maintain")["brake"], 0)
        self.assertEqual(MODULE.control_step(8, 160, 2, "brake")["brake"], 0)

    def test_original_history_positive_and_negative(self):
        for kind in MODULE.RIDER_KINDS:
            with self.subTest(kind=kind):
                self.assertEqual(MODULE.audit_original_history(history(kind),
                    expected_rider_kind=kind, expected_response="brake", map_sha256="a" * 64)["frames"], 3)
                with self.assertRaisesRegex(ValueError, "response"):
                    MODULE.audit_original_history(history(kind, 0), expected_rider_kind=kind,
                                                  expected_response="brake", map_sha256="a" * 64)

    def test_reject_requested_or_discontinuous_history(self):
        rows = history()
        rows[1]["source"] = "scripted_request"
        with self.assertRaisesRegex(ValueError, "original"):
            MODULE.audit_original_history(rows, expected_rider_kind="bicycle",
                                          expected_response="brake", map_sha256="a" * 64)
        rows = history()
        rows[1]["frame"] = 9
        with self.assertRaisesRegex(ValueError, "continuity"):
            MODULE.audit_original_history(rows, expected_rider_kind="bicycle",
                                          expected_response="brake", map_sha256="a" * 64)


if __name__ == "__main__":
    unittest.main()
