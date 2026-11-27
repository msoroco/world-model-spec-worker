"""Offline checks for the exact saved tunnel construction."""

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import check
from measure_tunnel import measure


class SelectedTunnelTest(unittest.TestCase):
    def setUp(self):
        self.bundle = Path(__file__).resolve().parents[1]

    def test_exact_bundle(self):
        self.assertEqual(check(self.bundle)["frames"], 600)

    def test_changed_source_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory)
            for name in ("config.json", "assignment-source.json", "road.xodr"):
                shutil.copyfile(self.bundle / name, copied / name)
            config = json.loads((copied / "config.json").read_text())
            config["road_sha256"] = "0" * 64
            (copied / "config.json").write_text(json.dumps(config) + "\n")
            with self.assertRaisesRegex(ValueError, "Changed source"):
                check(copied)

    def test_missing_original_source_rejected(self):
        source = {"source_kind": "original_native_tunnel_map_and_ray_readback",
                  "structure_kind": "tunnel", "approach_portal_x_m": 0,
                  "highway_centre_y_m": 0, "one_way_native_survey": False}
        with self.assertRaisesRegex(ValueError, "Missing source hash"):
            measure(source, [])


if __name__ == "__main__":
    unittest.main()
