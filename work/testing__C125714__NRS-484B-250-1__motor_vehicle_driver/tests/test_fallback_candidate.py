"""Check that the spawn fallback preserves every comparison condition."""
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def embedded(construction, name):
    return json.loads(next(item["content"] for item in construction["files"]
                           if item["path"] == name))


class SpawnFallbackTest(unittest.TestCase):
    def test_all_cases_change_only_initial_approach_points(self):
        manifest = json.loads((ROOT / "diagnostic-execution-manifest.json").read_text())
        self.assertEqual(len(manifest["cases"]), 7)
        for entry in manifest["cases"]:
            with self.subTest(case=entry["case_id"]):
                primary = json.loads((ROOT / entry["construction"]).read_text())
                candidate = entry["candidates"][0]
                path = ROOT / candidate["construction"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                                 candidate["construction_sha256"])
                alternate = json.loads(path.read_text())
                self.assertEqual(embedded(primary, "config.json"),
                                 embedded(alternate, "config.json"))
                old = embedded(primary, "scene.json")
                new = embedded(alternate, "scene.json")
                for party in ("ego", "other"):
                    key = party + "_route_xy_m"
                    self.assertNotEqual(old[key][0], new[key][0])
                    self.assertEqual(old[key][1:], new[key][1:])
                    old.pop(key)
                    new.pop(key)
                self.assertEqual(old, new)
                self.assertTrue(json.loads((ROOT / candidate["compatibility"]["receipt"]).read_text())
                                ["passed"])


if __name__ == "__main__":
    unittest.main()
