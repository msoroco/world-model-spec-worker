"""Synthetic protocol tests for authoring source-bound delivery candidates."""
import hashlib
import json
import subprocess
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from reviewed_delivery_author import (SUFFIXES, author, check_comparison_isolation,
                                      compatibility_manifest, source_files)
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
            validator = REPO / ".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck"
            self.assertTrue(validator.is_file(), "pinned Lean decoder must be built before proof")
            manifest = ROOT / ("protocol-compatibility-" + uuid.uuid4().hex + ".json")
            try:
                compatibility_manifest(output, manifest)
                for suffix in SUFFIXES:
                    for candidate in ("primary", "fallback1"):
                        completed = subprocess.run(
                            [sys.executable, str(REPO / "runtime.py"), "compatibility",
                             "--manifest", str(manifest),
                             "--case", ROOT.name + "__" + suffix,
                             "--candidate", candidate,
                             "--output", str(Path(proof) / ("compat-" + suffix + "-" + candidate)),
                             "--library", str(REPO / "runtime/library"),
                             "--validator", str(validator)], cwd=REPO, capture_output=True,
                            text=True, timeout=180)
                        self.assertEqual(completed.returncode, 0, suffix + "/" + candidate +
                                         ": " + completed.stderr + completed.stdout)
                        receipt_root = Path(proof) / ("compat-" + suffix + "-" + candidate)
                        receipt = json.loads((receipt_root / "compatibility.json").read_text())
                        self.assertIs(receipt["passed"], True)
                        self.assertEqual(receipt["case_id"], ROOT.name + "__" + suffix)
                        self.assertEqual(receipt["candidate_id"], candidate)
                        self.assertIn(receipt["negative_error_contains"],
                                      (receipt_root / "negative-analysis.log").read_text())
            finally:
                manifest.unlink(missing_ok=True)
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
            with self.assertRaisesRegex(ValueError, "fixed scene field"):
                author(source, ROOT / "candidate-map.xodr", Path(destination) / "candidate",
                       Path(proof) / "preflight")
            scenes = {suffix: json.loads((Path(source) / suffix / "scene.json").read_text())
                      for suffix in SUFFIXES}
            scenes["other_later"]["ego_route_xy_m"][0][0] -= 1
            check_comparison_isolation(scenes)
            scenes["opposite_intends_left"]["other_highway"] = "changed"
            with self.assertRaisesRegex(ValueError, "fixed scene field"):
                check_comparison_isolation(scenes)
            scenes["opposite_intends_left"]["other_highway"] = scenes["opposite_straight"]["other_highway"]
            scenes["wide_same_crossing"]["crossing"]["roadway_id"] = scenes["precedence"]["crossing"]["roadway_id"]
            with self.assertRaisesRegex(ValueError, "distinct roadway_id"):
                check_comparison_isolation(scenes)

    def test_rejects_packet_and_source_aliases_before_bundling(self):
        with TemporaryDirectory() as source:
            fixture(source)
            folder = Path(source) / "precedence"
            scene_path = folder / "scene.json"
            scene = json.loads(scene_path.read_text())
            packet_path = folder / "reviewed-context.json"
            alias = folder / "packet-alias.json"
            alias.symlink_to(packet_path.name)
            scene["reviewed_context_source"] = alias.name
            scene_path.write_text(json.dumps(scene))
            with self.assertRaisesRegex(ValueError, "packet cannot be a symlink"):
                source_files(scene_path)
            alias.unlink()

            scene["reviewed_context_source"] = "../precedence/reviewed-context.json"
            scene_path.write_text(json.dumps(scene))
            with self.assertRaisesRegex(ValueError, "packet must be case relative"):
                source_files(scene_path)

            scene["reviewed_context_source"] = packet_path.name
            scene_path.write_text(json.dumps(scene))
            packet = json.loads(packet_path.read_text())
            descriptor = packet["law_context"]["device_inventory_source"]
            original = folder / descriptor["source_path"]
            source_alias = folder / "source-alias.txt"
            source_alias.symlink_to(original.name)
            descriptor["source_path"] = source_alias.name
            packet_path.write_text(json.dumps(packet))
            scene["reviewed_context_sha256"] = sha(packet_path)
            scene_path.write_text(json.dumps(scene))
            with self.assertRaisesRegex(ValueError, "review source cannot be a symlink"):
                source_files(scene_path)

            source_alias.unlink()
            descriptor["source_path"] = "../precedence/" + original.name
            packet_path.write_text(json.dumps(packet))
            scene["reviewed_context_sha256"] = sha(packet_path)
            scene_path.write_text(json.dumps(scene))
            with self.assertRaisesRegex(ValueError, "source path must be packet relative"):
                source_files(scene_path)

    def test_preserves_reviewed_crlf_bytes_in_construction(self):
        with TemporaryDirectory() as source:
            fixture(source)
            folder = Path(source) / "precedence"
            scene_path = folder / "scene.json"
            packet_path = folder / "reviewed-context.json"
            packet = json.loads(packet_path.read_text())
            descriptor = packet["law_context"]["device_inventory_source"]
            original = folder / descriptor["source_path"]
            original.write_bytes(b"reviewed line one\r\nreviewed line two\r\n")
            descriptor["source_sha256"] = sha(original)
            packet_path.write_bytes(json.dumps(packet, indent=2).replace("\n", "\r\n").encode())
            scene = json.loads(scene_path.read_text())
            scene["reviewed_context_sha256"] = sha(packet_path)
            scene_path.write_text(json.dumps(scene))
            _, files = source_files(scene_path)
            self.assertEqual(files["reviewed-context.json"].encode(), packet_path.read_bytes())
            self.assertEqual(files[original.name].encode(), original.read_bytes())


if __name__ == "__main__":
    unittest.main()
