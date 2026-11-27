"""Original reviewed site hashes must bind every construction input byte."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from school_pass import SOURCES
from school_scene_construction import validate_site
from test_school_pass import scene


class SiteSourceTests(unittest.TestCase):
    def test_site_source_hashes_and_negative_tamper(self):
        scratch = Path(os.environ["TMPDIR"])
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            site = scene()
            records = {}
            for name in SOURCES:
                source = root / (name + ".json")
                source.write_text(json.dumps({"source": name, "reviewed": True}) + "\n")
                digest = hashlib.sha256(source.read_bytes()).hexdigest()
                site[name + "_source_sha256"] = digest
                records[name] = {"path": source.name, "sha256": digest}
            site["source_records"] = records
            site["map_sha256"] = records["map_geometry"]["sha256"]
            for field, name in {
                "calendar_source_sha256": "school_calendar",
                "operation_schedule_source_sha256": "operation_schedule",
                "class_schedule_source_sha256": "class_schedule",
                "local_clock_source_sha256": "local_clock",
                "beacon_configuration_source_sha256": "beacon_configuration",
                "beacon_state_source_sha256": "beacon_state",
                "sign_instruction_source_sha256": "sign_instruction",
                "zone_designation_source_sha256": "zone_designation",
            }.items():
                site["timing_packet"][field] = records[name]["sha256"]
            path = root / "site.json"
            path.write_text(json.dumps(site, sort_keys=True) + "\n")
            self.assertEqual(validate_site(path, site["case_id"])["_source_sha256"],
                             hashlib.sha256(path.read_bytes()).hexdigest())
            (root / "map_geometry.json").write_text('{"tampered":true}\n')
            with self.assertRaisesRegex(ValueError, "source hash differs"):
                validate_site(path, site["case_id"])

    def test_source_outside_packet_rejected(self):
        scratch = Path(os.environ["TMPDIR"])
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            path = Path(directory) / "site.json"
            site = scene()
            site["source_records"] = {name: {"path": "../outside", "sha256": "0" * 64}
                                      for name in SOURCES}
            path.write_text(json.dumps(site) + "\n")
            with self.assertRaisesRegex(ValueError, "outside original site packet"):
                validate_site(path, site["case_id"])


if __name__ == "__main__":
    unittest.main()
