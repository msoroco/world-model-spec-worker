"""Source custody protocol tests use synthetic bytes and claim no site review."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from reviewed_site import BASE_SOURCES, EXCEPTION_SOURCE, exact_specs, verify
from test_parking import site


class ReviewedSiteTests(unittest.TestCase):
    def make_packet(self, root):
        root = Path(root)
        sources = root / "sources"
        sources.mkdir()
        selected = site()
        inventory = {}
        for key in (*BASE_SOURCES, *EXCEPTION_SOURCE.values()):
            path = sources / (key + ".txt")
            path.write_text("synthetic " + key + "\n")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            selected[key + "_sha256"] = digest
            inventory[key] = {"path": path.name, "sha256": digest,
                              "reviewer": "fixture test", "citation": "synthetic protocol"}
        packet = {"assignment_id": HERE.name, "reviewer": "fixture test",
                  "citation": "synthetic protocol", "site": selected, "sources": inventory}
        path = root / "reviewed-site.json"
        path.write_text(json.dumps(packet) + "\n")
        return path, sources, packet

    def test_twelve_exact_specs_are_source_bound(self):
        scratch = Path(".runtime-work/c150153-reviewed-site-tests")
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as tmp:
            path, sources, _ = self.make_packet(tmp)
            specs = exact_specs(path, sources, 4.0)
            self.assertEqual(len(specs["cases"]), 12)
            self.assertEqual(len({c["case_id"] for c in specs["cases"]}), 12)
            self.assertEqual(specs["status"], "source_bound_unproven")
            self.assertEqual({c["capture_frames"] for c in specs["cases"]}, {900})
            output = scratch / (Path(tmp).name + "-specs.json")
            command = [sys.executable, str(HERE / "reviewed_site.py"),
                       "--packet", str(path), "--source-root", str(sources),
                       "--body-length-m", "4", "--output", str(output)]
            subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertEqual(json.loads(output.read_text()), specs)
            output.unlink()

    def test_changed_source_and_missing_review_fail_closed(self):
        scratch = Path(".runtime-work/c150153-reviewed-site-tests")
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as tmp:
            path, sources, packet = self.make_packet(tmp)
            (sources / "map.txt").write_text("changed\n")
            with self.assertRaisesRegex(ValueError, "hash differs: map"):
                verify(path, sources)
            (sources / "map.txt").write_text("synthetic map\n")
            packet["sources"]["map"]["reviewer"] = ""
            path.write_text(json.dumps(packet) + "\n")
            with self.assertRaisesRegex(ValueError, "review missing: map"):
                verify(path, sources)

    def test_source_escape_and_missing_exception_are_rejected(self):
        scratch = Path(".runtime-work/c150153-reviewed-site-tests")
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as tmp:
            path, sources, packet = self.make_packet(tmp)
            packet["sources"]["police_direction_source"]["path"] = "../outside.txt"
            path.write_text(json.dumps(packet) + "\n")
            with self.assertRaisesRegex(ValueError, "escapes root"):
                verify(path, sources)
            packet["sources"].pop("police_direction_source")
            path.write_text(json.dumps(packet) + "\n")
            with self.assertRaisesRegex(ValueError, "inventory incomplete"):
                verify(path, sources)


if __name__ == "__main__":
    unittest.main()
