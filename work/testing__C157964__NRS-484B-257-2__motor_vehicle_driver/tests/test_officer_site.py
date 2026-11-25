import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from officer_site import SITE, validate_site


class OfficerSiteTests(unittest.TestCase):
    def test_signed_one_way_to_two_way_junction(self):
        site = validate_site()
        self.assertEqual(site["ego_road_id"], 157960)
        self.assertEqual(site["through_approaches"], [[157964, -1], [157966, 1]])
        self.assertFalse(site["signal_controller_present"])
        self.assertEqual(site["physical_sign_and_view_status"], "unverified")

    def test_missing_sign_or_opposite_approach_rejected(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "site.xodr"
            source = SITE.read_text()
            path.write_text(source.replace('type="205"', 'type="999"', 1))
            with self.assertRaisesRegex(ValueError, "signed ego entrance"):
                validate_site(path)
            path.write_text(source.replace('id="157966"', 'id="157967"', 1))
            with self.assertRaisesRegex(ValueError, "road inventory differs"):
                validate_site(path)


if __name__ == "__main__":
    unittest.main()
