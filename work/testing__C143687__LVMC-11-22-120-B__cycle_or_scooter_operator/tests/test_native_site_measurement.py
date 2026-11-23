import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_site import canonical_sha, command_bicycle, spawn_bicycle, validate_site
from native_measurement import measure
from comparison_audit import audit_pair


def site():
    return {
        "map_name": "sourced_map", "jurisdiction_source": "original_city_boundary_packet",
        "engineer_designation_source": "original_engineer_designation_packet", "street_id": "street-1",
        "designation_street_id": "street-1", "designation_prohibits_bicycle_roadway_use": True,
        "bicycle_blueprint_id": "vehicle.bicycle", "engineering_speed_mps": 3.0,
        "route_segments": [
            {"kind": "nonmotorized_trail", "start": [-10, 0, 0], "end": [0, 0, 0]},
            {"kind": "governed_street_roadway", "street_id": "street-1", "start": [0, 0, 0], "end": [10, 0, 0]},
        ],
        "sign": {"source_id": "sign-1", "wording": "BICYCLES PROHIBITED ON ROADWAY",
                 "facing_direction": "eastbound", "erection_source": "original_sign_installation_packet",
                 "position": [-1, 1, 0], "street_id": "street-1", "posted": True,
                 "prohibits_bicycle_roadway_use": True},
    }


class Vector:
    def __init__(self, x=0, y=0, z=0):
        self.x, self.y, self.z = x, y, z


class Bike:
    id = 23
    is_alive = True
    type_id = "vehicle.bicycle"

    def set_target_velocity(self, value):
        self.velocity = value

    def get_velocity(self):
        return self.velocity


class World:
    def __init__(self):
        self.calls = []

    def get_blueprint_library(self):
        self.calls.append("library")
        return self

    def find(self, blueprint_id):
        self.calls.append(("find", blueprint_id))
        return blueprint_id

    def try_spawn_actor(self, blueprint, transform):
        self.calls.append(("spawn", blueprint, transform))
        return Bike()


def packet(s, case_id, enter):
    rows = []
    for i in range(900):
        rows.append({"original_frame": i, "elapsed_s": i / 20, "actor_id": "23",
                     "segment": "governed_street_roadway" if enter and i >= 200 else "nonmotorized_trail",
                     "street_id": "street-1", "sign_source_id": "sign-1", "sign_posted_readback": True})
    result = {"source_kind": "original_native_capture", "case_id": case_id,
              "site_sha256": canonical_sha(s), "map_name": s["map_name"],
              "street_id": "street-1", "actor_id": "23", "actor_blueprint_id": "vehicle.bicycle",
              "frames": rows}
    result["seal_sha256"] = canonical_sha(result)
    return result


class TestNativeSource(unittest.TestCase):
    def test_route_validation_and_native_calls(self):
        s = site()
        world = World()
        bike = spawn_bicycle(world, "source_transform", s)
        self.assertEqual(world.calls[-1], ("spawn", "vehicle.bicycle", "source_transform"))
        carla = type("Carla", (), {"Vector3D": Vector})
        row = command_bicycle(bike, carla, s, {"motion": "enter_roadway"}, 4.0)
        self.assertEqual(row["observed_velocity_mps"], [3.0, 0.0, 0.0])
        held = command_bicycle(bike, carla, s, {"motion": "stop_before_roadway"}, 4.0)
        self.assertEqual(held["observed_velocity_mps"], [0.0, 0.0, 0.0])

    def test_source_gate_rejects_nonapplicable_and_disconnected_sign(self):
        s = site()
        s["sign"]["prohibits_bicycle_roadway_use"] = False
        with self.assertRaisesRegex(ValueError, "posted sign"):
            validate_site(s)
        s = site()
        s["route_segments"][1]["start"] = [50, 0, 0]
        with self.assertRaisesRegex(ValueError, "connect"):
            validate_site(s)
        s = site()
        s["designation_street_id"] = "other"
        with self.assertRaisesRegex(ValueError, "designation"):
            validate_site(s)

    def test_original_saved_measurement_and_negative_proofs(self):
        s = site()
        enter_case = {"case_id": "case-enter", "motion": "enter_roadway"}
        keep_case = {"case_id": "case-keep", "motion": "remain_trail"}
        crossing = packet(s, "case-enter", True)
        self.assertEqual(measure(s, crossing, enter_case)["first_roadway_frame"], 200)
        self.assertEqual(measure(s, packet(s, "case-keep", False), keep_case)["roadway_frames"], 0)
        crossing["frames"][20]["sign_posted_readback"] = False
        with self.assertRaisesRegex(ValueError, "seal"):
            measure(s, crossing, enter_case)
        crossing["seal_sha256"] = canonical_sha({k: v for k, v in crossing.items() if k != "seal_sha256"})
        with self.assertRaisesRegex(ValueError, "sign readback"):
            measure(s, crossing, enter_case)
        nonentry = packet(s, "case-enter", False)
        with self.assertRaisesRegex(ValueError, "entry not observed"):
            measure(s, nonentry, enter_case)

    def test_comparison_audit_holds_source_site_fixed(self):
        s = site()
        names = ["case-enter", "case-stop", "case-remain"]
        plan = {"comparisons": [
            {"comparison_id": "posted_roadway_entry", "case_ids": names[:2]},
            {"comparison_id": "trail_vs_roadway_use", "case_ids": [names[0], names[2]]},
        ]}
        enter = measure(s, packet(s, names[0], True), {"case_id": names[0], "motion": "enter_roadway"})
        stop = measure(s, packet(s, names[1], False), {"case_id": names[1], "motion": "stop_before_roadway"})
        remain = measure(s, packet(s, names[2], False), {"case_id": names[2], "motion": "remain_trail"})
        self.assertEqual(audit_pair(plan, enter, stop, "posted_roadway_entry")["legal_assessment"], "unresolved")
        self.assertEqual(audit_pair(plan, enter, remain, "trail_vs_roadway_use")["case_ids"], [names[0], names[2]])
        with self.assertRaisesRegex(ValueError, "fixed"):
            audit_pair(plan, enter, {**stop, "site_sha256": "wrong"}, "posted_roadway_entry")
        with self.assertRaisesRegex(ValueError, "contrast"):
            audit_pair(plan, {**enter, "roadway_frames": 0}, stop, "posted_roadway_entry")
        with self.assertRaisesRegex(ValueError, "incomplete"):
            audit_pair(plan, enter, {**stop, "frames": 899}, "posted_roadway_entry")


if __name__ == "__main__":
    unittest.main()
