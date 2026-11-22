"""Synthetic protocol tests for authoring source-bound delivery candidates."""
import hashlib
import json
import subprocess
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from reviewed_delivery_author import SUFFIXES, author, source_files
from case_builder import config


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixture(base):
    for suffix in SUFFIXES:
        original = ROOT if suffix == "precedence" else ROOT / "cases" / suffix
        scene = json.loads((original / "scene.json").read_text())
        packet = json.loads((original / "diagnostic-context.json").read_text())
        scene["diagnostic_only"] = packet["diagnostic_only"] = False
        law = packet["law_context"]
        law["public_access"] = law["human_driver"] = True
        folder = Path(base) / suffix
        folder.mkdir(parents=True)
        for key in ("public_access_source", "device_inventory_source", "driver_scope_source"):
            source = folder / (key + ".txt")
            source.write_text("synthetic protocol fixture for " + key + "\n")
            law[key] = {"source_path": source.name, "source_sha256": sha(source),
                        "reviewer": "CPU protocol fixture", "source_citation": "fixture only"}
        packet_path = folder / "reviewed-context.json"
        packet_path.write_text(json.dumps(packet))
        scene["reviewed_context_source"] = packet_path.name
        scene["reviewed_context_sha256"] = sha(packet_path)
        (folder / "scene.json").write_text(json.dumps(scene))


class ReviewedDeliveryAuthorTest(unittest.TestCase):
    def test_authors_all_exact_candidates_and_rejects_changed_source(self):
        with TemporaryDirectory() as source, TemporaryDirectory(dir=ROOT) as destination, \
             TemporaryDirectory(dir=REPO / ".runtime-work") as proof:
            fixture(source)
            output = Path(destination) / "candidate"
            receipts = Path(proof) / "preflight"
            result = author(source, ROOT / "candidate-map.xodr", output, receipts)
            self.assertEqual(len(result["cases"]), 7)
            self.assertTrue(all((output / suffix / "construction.json").is_file()
                                for suffix in SUFFIXES))
            self.assertTrue(all((receipts / suffix / "preflight.json").is_file()
                                for suffix in SUFFIXES))
            construction = json.loads((output / "advance" / "construction.json").read_text())
            self.assertFalse(construction["diagnostic_only"])
            self.assertIn("precedence_response_audit.py",
                          {item["path"] for item in construction["files"]})
            fallback = json.loads((output / "advance" / "fallback1-construction.json").read_text())
            primary_files = {item["path"]: item["content"] for item in construction["files"]}
            fallback_files = {item["path"]: item["content"] for item in fallback["files"]}
            self.assertEqual(primary_files["reviewed-context.json"],
                             fallback_files["reviewed-context.json"])
            self.assertEqual(primary_files["reviewed-map.xodr"],
                             fallback_files["reviewed-map.xodr"])
            fallback_scene = json.loads(fallback_files["scene.json"])
            self.assertEqual(json.loads(fallback_files["config.json"]), config(fallback_scene))
            self.assertNotEqual(primary_files["scene.json"], fallback_files["scene.json"])
            for suffix in SUFFIXES:
                for candidate in ("primary", "fallback1"):
                    completed = subprocess.run(
                        [sys.executable, str(REPO / "runtime.py"), "offline",
                         "--manifest", str(output / "candidate-index.json"),
                         "--case", ROOT.name + "__" + suffix, "--candidate", candidate,
                         "--output", str(Path(proof) / ("offline-" + suffix + "-" + candidate)),
                         "--python", sys.executable], cwd=REPO, capture_output=True,
                        text=True, timeout=60)
                    self.assertEqual(completed.returncode, 0, suffix + "/" + candidate + ": " +
                                     completed.stderr + completed.stdout)
            tampered = Path(source) / "precedence" / "device_inventory_source.txt"
            tampered.write_text("changed")
            with self.assertRaisesRegex(ValueError, "reviewed source hash changed"):
                author(source, ROOT / "candidate-map.xodr", Path(destination) / "other",
                       Path(proof) / "other")

    def test_rejects_diagnostic_and_unisolated_pair(self):
        with self.assertRaisesRegex(ValueError, "rejects diagnostic"):
            source_files(ROOT / "scene.json")
        with TemporaryDirectory() as source, TemporaryDirectory(dir=ROOT) as destination, \
             TemporaryDirectory(dir=REPO / ".runtime-work") as proof:
            fixture(source)
            scene_path = Path(source) / "other_later" / "scene.json"
            scene = json.loads(scene_path.read_text())
            scene["ego_route_xy_m"][0][0] += 1
            scene_path.write_text(json.dumps(scene))
            with self.assertRaisesRegex(ValueError, "comparison is not isolated"):
                author(source, ROOT / "candidate-map.xodr", Path(destination) / "candidate",
                       Path(proof) / "preflight")


if __name__ == "__main__":
    unittest.main()
