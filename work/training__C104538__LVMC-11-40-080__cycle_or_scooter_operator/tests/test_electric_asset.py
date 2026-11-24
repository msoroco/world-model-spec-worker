import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "native"))
from electric_asset import validate_blueprint


class Blueprint:
    def __init__(self, blueprint_id):
        self.id = blueprint_id


class Library:
    def __init__(self, ids):
        self.ids = ids

    def filter(self, pattern):
        return [Blueprint(item) for item in self.ids if item == pattern]


class ElectricAssetTest(unittest.TestCase):
    def test_rejects_bicycle_alias_for_both_electric_classes(self):
        for machine_class in ("electric_bicycle", "electric_scooter"):
            with self.subTest(machine_class=machine_class):
                evidence = {"machine_class": machine_class,
                            "blueprint_id": "vehicle.bh.crossbike",
                            "source_kind": "reviewed_native_asset", "reviewer": "asset-review"}
                with self.assertRaisesRegex(ValueError, "Ordinary bicycle"):
                    validate_blueprint(Library(["vehicle.bh.crossbike"]),
                                       machine_class, "vehicle.bh.crossbike", evidence)

    def test_requires_exact_live_asset_and_review(self):
        evidence = {"machine_class": "electric_bicycle",
                    "blueprint_id": "vehicle.example.electric_bicycle",
                    "source_kind": "reviewed_native_asset", "reviewer": "asset-review"}
        with self.assertRaisesRegex(ValueError, "unavailable"):
            validate_blueprint(Library([]), "electric_bicycle",
                               evidence["blueprint_id"], evidence)
        self.assertTrue(validate_blueprint(Library([evidence["blueprint_id"]]),
                                           "electric_bicycle", evidence["blueprint_id"],
                                           evidence)["native_asset_found"])
        evidence["source_kind"] = "synthetic_label"
        with self.assertRaisesRegex(ValueError, "Reviewed"):
            validate_blueprint(Library([evidence["blueprint_id"]]),
                               "electric_bicycle", evidence["blueprint_id"], evidence)
