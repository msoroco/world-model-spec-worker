import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

from test_passenger_zone import site
from test_saved_audit import rows


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("zone_finalize_saved", ROOT / "finalize_saved.py")
finalizer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = finalizer
spec.loader.exec_module(finalizer)


class FinalizerTests(unittest.TestCase):
    def prepare(self, folder):
        root = Path(folder)
        s = site()
        site_path = root / "site.json"
        site_path.write_text(json.dumps(s))
        data = rows()
        for row in data:
            row["ego_center_xy"] = [4, 1]
            row["ego_speed_mps"] = 0.0
            row["zone_source_sha256"] = s["zone"]["boundary_source_sha256"]
        history = root / "history.jsonl"
        history.write_text("".join(json.dumps(row) + "\n" for row in data))
        seal = root / "seal.json"
        seal.write_text(json.dumps({"case_id": "load_prompt", "site_sha256": finalizer.digest(site_path),
                                    "original_history_sha256": finalizer.digest(history)}))
        return site_path, history, seal, root / "result.json"

    def test_saved_only_finalizer(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = self.prepare(folder)
            result = finalizer.finalize(paths[1], paths[0], paths[2], paths[3])
            self.assertEqual(result["measurement"]["passenger_event_count"], 1)
            self.assertEqual(result["measurement"]["in_zone_halted_frame_count"], 900)
            self.assertIsNone(result["legal_judgment"])
            self.assertEqual(json.loads(paths[3].read_text())["original_history_sha256"], finalizer.digest(paths[1]))

    def test_rejects_stale_site_and_history(self):
        for target in ("site", "history"):
            with tempfile.TemporaryDirectory() as folder:
                site_path, history, seal, output = self.prepare(folder)
                path = site_path if target == "site" else history
                path.write_text(path.read_text() + " ")
                with self.assertRaises(ValueError):
                    finalizer.finalize(history, site_path, seal, output)
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
