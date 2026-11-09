import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("audit", ROOT / "audit.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class AuditTests(unittest.TestCase):
    def test_comparison_holds_controller_fixed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            paths = [base / "near", base / "far"]
            for path, gap in zip(paths, (16.0, 26.0)):
                path.mkdir()
                config = json.loads((ROOT / "config.json").read_text())
                config["initial_gap_m"] = gap
                (path / "config.json").write_text(json.dumps(config))
                (path / "surface_context.json").write_text(json.dumps({
                    "map": "synthetic", "road_id": 1, "crest_location_m": [0, 0, 5],
                    "initial_lane_id": -1, "target_lane_id": -2}))
            self.assertEqual(AUDIT.compare(*paths)["comparison_id"], "crest_follow_gap")
            changed = json.loads((paths[1] / "config.json").read_text())
            changed["controller"]["lookahead_m"] = 11
            (paths[1] / "config.json").write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "fixed condition differs"):
                AUDIT.compare(*paths)


if __name__ == "__main__":
    unittest.main()
