import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("site_source", ROOT / "site_source.py")
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)


class SiteTests(unittest.TestCase):
    def test_all_entering_lanes_and_devices(self):
        result = site.inventory(ROOT / "signal-site.xodr")
        self.assertEqual({row["lane_key"]: row["device"] for row in result["entrances"]},
                         {"158190:-1":"yield", "158194:-1":"none", "158196:1":"none"})
        self.assertTrue(result["legal_site_review_pending"])
        self.assertTrue(result["native_signal_governance_review_pending"])
        self.assertTrue(result["authored_signal_governs_ego"])
        stop = site.inventory(ROOT / "stop-site.xodr")
        self.assertEqual(next(row["device"] for row in stop["entrances"]
                              if row["lane_key"] == "158190:-1"), "stop")
        self.assertNotEqual(result["source_sha256"], stop["source_sha256"])
        elsewhere = site.inventory(ROOT / "visible-site.xodr")
        self.assertFalse(elsewhere["authored_signal_governs_ego"])
        self.assertEqual(elsewhere["signal_head_lane_key"], "158194:-1")

    def test_changed_other_sign_and_missing_entrance_rejected(self):
        original = (ROOT / "signal-site.xodr").read_text()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "signal-site.xodr"
            path.write_text(original.replace('<road name="two-way through south" length="72" id="158194" junction="-1">',
                                             '<road name="two-way through south" length="72" id="158194" junction="-1"><signals><signal id="x" dynamic="no" type="205"><validity fromLane="-1" toLane="-1" /></signal></signals>'))
            with self.assertRaisesRegex(ValueError, "non-obligated"):
                site.inventory(path)
            path.write_text(original.replace('incomingRoad="158196" connectingRoad="158195"',
                                             'incomingRoad="158194" connectingRoad="158195"'))
            with self.assertRaisesRegex(ValueError, "entering lanes"):
                site.inventory(path)


if __name__ == "__main__":
    unittest.main()
