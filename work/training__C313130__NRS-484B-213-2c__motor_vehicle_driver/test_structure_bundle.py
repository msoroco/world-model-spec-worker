"""Materialized bridge and viaduct construction checks."""

import json
from pathlib import Path
import unittest

from runner import check
from structure_variant import request, validate


class BundleTests(unittest.TestCase):
    def test_exact_runner(self):
        bundle = Path(__file__).resolve().parent.parent
        result = check(bundle)
        self.assertEqual(result["frames"], 600)
        self.assertFalse(result["native_executed"])

    def test_fixed_source(self):
        bundle = Path(__file__).resolve().parent.parent
        config = json.loads((bundle / "config.json").read_text())
        variant = request(config["structure_kind"], config["requested_lateral_target"])
        self.assertFalse(validate(variant)["physical_structure_verified"])
        self.assertEqual((bundle / "road.xodr").read_text(), variant["road_opendrive"])


if __name__ == "__main__":
    unittest.main()
