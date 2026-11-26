import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("branch_alternatives", ROOT / "branch_alternatives.py")
branch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(branch)


def original():
    return {"source_kind": "original_native_observation",
            "subject_approach_source_id": "frame-map:000220",
            "authorized_vehicle_source_id": "actor-survey:emergency",
            "vehicle_kind": "authorized_emergency_vehicle",
            "flashing_equipment_source_id": "equipment-review:1",
            "flashing_pixel_source_id": "camera-review:000220",
            "flashing_qualification_source_id": "qualification-review:1",
            "officer_direction_source_id": "scene-review:1",
            "road_context_source_id": "road-survey:1",
            "weather_context_source_id": "weather-observation:1",
            "already_moving": True,
            "visible_vehicle_movement": False,
            "visible_driver_hand_signal": False,
            "officer_directed": False}


class BranchAlternativesTest(unittest.TestCase):
    def test_already_moving_and_exception_absent(self):
        row = branch.classify(original())
        self.assertEqual(row["observed_activation_branches"], ["already_moving"])
        self.assertEqual(row["disposition"], "speed_decrease_measurement_required")
        self.assertFalse(row["legal_outcome_claimed"])

    def test_visible_vehicle_movement(self):
        row = original()
        row.update(already_moving=False, visible_vehicle_movement=True,
                   movement_pixel_source_id="camera-review:000220")
        self.assertEqual(branch.classify(row)["observed_activation_branches"],
                         ["visible_vehicle_movement"])

    def test_visible_hand_signal(self):
        row = original()
        row.update(already_moving=False, visible_driver_hand_signal=True,
                   hand_signal_pixel_source_id="camera-review:000220",
                   hand_signal_actor_source_id="actor-review:driver")
        self.assertEqual(branch.classify(row)["observed_activation_branches"],
                         ["visible_driver_hand_signal"])

    def test_officer_instruction_exception(self):
        row = original()
        row.update(officer_directed=True, officer_instruction_source_id="officer-review:1")
        self.assertEqual(branch.classify(row)["disposition"],
                         "officer_direction_exception_review")

    def test_rejects_unseen_hand_signal(self):
        row = original()
        row.update(already_moving=False, visible_driver_hand_signal=True,
                   hand_signal_actor_source_id="actor-review:driver")
        with self.assertRaisesRegex(ValueError, "Visible driver hand signal source missing"):
            branch.classify(row)

    def test_rejects_unobserved_activation(self):
        row = original()
        row["already_moving"] = False
        with self.assertRaisesRegex(ValueError, "No observed moving"):
            branch.classify(row)

    def test_rejects_unsourced_exception(self):
        row = original()
        row["officer_directed"] = True
        with self.assertRaisesRegex(ValueError, "Officer instruction source missing"):
            branch.classify(row)

    def test_rejects_synthetic_and_missing_lamp_pixels(self):
        row = original()
        row["source_kind"] = "synthetic_cpu_fixture"
        with self.assertRaisesRegex(ValueError, "Original Native source required"):
            branch.classify(row)
        row = original()
        row.pop("flashing_pixel_source_id")
        with self.assertRaisesRegex(ValueError, "flashing light sources missing"):
            branch.classify(row)
