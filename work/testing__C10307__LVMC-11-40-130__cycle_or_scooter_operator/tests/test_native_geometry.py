import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_geometry import opendrive_text, validate_geometry


class GeometryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.map = Path(self.tmp.name) / "alley.xodr"
        self.map.write_text(opendrive_text())

    def test_route_and_rack_envelope(self):
        checked = validate_geometry(self.map)
        self.assertEqual(checked["route_xy_m"], [[-30.0, -0.75], [30.0, -0.75]])
        self.assertFalse(checked["rack_visual_asset_verified"])

    def test_missing_map_rejected(self):
        self.map.unlink()
        with self.assertRaises(FileNotFoundError):
            validate_geometry(self.map)

    def test_rack_intrusion_rejected(self):
        with self.assertRaisesRegex(ValueError, "intrudes"):
            validate_geometry(self.map, (-1, 1.8, 1, 2.5))

    def test_changed_map_rejected(self):
        self.map.write_text(opendrive_text().replace('length="80"', 'length="60"'))
        with self.assertRaisesRegex(ValueError, "differs"):
            validate_geometry(self.map)


if __name__ == "__main__":
    unittest.main()
