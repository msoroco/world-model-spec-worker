import importlib.util
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "door_interaction.py"
spec = importlib.util.spec_from_file_location("door_interaction", SOURCE)
door = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = door
spec.loader.exec_module(door)
P = door.Point


class DoorInteractionTests(unittest.TestCase):
    def test_both_passing_sides_and_actual_command(self):
        self.assertEqual(door.traffic_side(P(1, 0), P(0, 0),
                                           [P(-2, 1.4), P(2, 1.4)]), "left")
        self.assertEqual(door.traffic_side(P(1, 0), P(0, 0),
                                           [P(-2, -1.4), P(2, -1.4)]), "right")

        class Carla:
            class VehicleDoor:
                FL = "front_left"
                FR = "front_right"

        class Vehicle:
            def __init__(self):
                self.calls = []

            def open_door(self, selected):
                self.calls.append(selected)

        vehicle = Vehicle()
        door.request_door_open(vehicle, Carla, "left")
        door.request_door_open(vehicle, Carla, "right")
        self.assertEqual(vehicle.calls, ["front_left", "front_right"])

    def test_moving_open_near_side_proximity_and_controls(self):
        arguments = dict(parked_center=P(0, 0), parked_heading=P(1, 0),
                         door_side="left", synchronized_frame_ids=[10, 11, 12],
                         passing_speed_samples_mps=[5, 5, 5],
                         door_open_samples=[False, True, True],
                         vehicle_half_width_m=0.8)
        near = door.interaction_measurement(
            **arguments, passing_path=[P(-2, 1.5), P(0.75, 1.5), P(2, 1.5)])
        self.assertTrue(near["opening_on_passing_side"])
        self.assertTrue(near["proxy_overlap_present"])
        self.assertEqual(near["legal_interference"], "unresolved_judgment")
        far = door.interaction_measurement(
            **arguments, passing_path=[P(-2, 4), P(0.75, 4), P(2, 4)])
        self.assertFalse(far["proxy_overlap_present"])
        opposite = door.interaction_measurement(
            **{**arguments, "door_side": "right"},
            passing_path=[P(-2, 1.5), P(0.75, 1.5), P(2, 1.5)])
        self.assertFalse(opposite["opening_on_passing_side"])
        self.assertFalse(opposite["proxy_overlap_present"])

    def test_rejects_source_gaps_and_ambiguous_geometry(self):
        with self.assertRaises(ValueError):
            door.traffic_side(P(1, 0), P(0, 0), [P(-2, 1), P(2, -1)])
        with self.assertRaises(ValueError):
            door.interaction_measurement(
                parked_center=P(0, 0), parked_heading=P(1, 0),
                door_side="left", passing_path=[P(-2, 1), P(2, 1)],
                passing_speed_samples_mps=[5, 5], door_open_samples=[True],
                synchronized_frame_ids=[10, 11], vehicle_half_width_m=0.8)
        self.assertEqual(door.segment_distance(P(0, 0), P(2, 0),
                                               P(1, -1), P(1, 1)), 0)

    def test_loading_site_has_real_grade_reversal_and_spatial_binding(self):
        measured = door.inspect_loading_crest([(0, 0), (10, 1), (20, 0)],
                                               12, P(12, 3),
                                               (P(0, 2), P(20, 2)))
        self.assertEqual(measured["crest_station_m"], 10)
        self.assertEqual(measured["loading_to_crest_m"], 2)
        self.assertEqual(measured["loading_to_road_edge_m"], 1)
        self.assertEqual(measured["legal_hill_crest_proximity"],
                         "unresolved_judgment")
        with self.assertRaises(ValueError):
            door.inspect_loading_crest([(0, 0), (10, 0), (20, 1)], 12,
                                       P(12, 3), (P(0, 2), P(20, 2)))


if __name__ == "__main__":
    unittest.main()
