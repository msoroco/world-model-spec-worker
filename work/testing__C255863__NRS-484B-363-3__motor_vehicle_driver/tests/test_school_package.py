"""Synthetic CPU checks for source binding and selected school analysis."""

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from school_scene_construction import ASSIGNMENT, validate_site
from school_uturn import CASES, SOURCES
from test_school_uturn import scene


class SchoolPackageTests(unittest.TestCase):
    def test_reviewed_packet_hashes_are_independent(self):
        case = CASES[0]
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as folder:
            root = Path(folder)
            packet = scene(case)
            packet["case_id"] = ASSIGNMENT + "__" + case.name
            packet["map_sha256"] = hashlib.sha256(b"diagnostic map").hexdigest()
            records = {}
            for name in SOURCES:
                path = root / (name + ".txt")
                path.write_text("synthetic diagnostic " + name + "\n")
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                records[name] = {"path": path.name, "sha256": digest}
                packet[name + "_source_sha256"] = digest
            packet["source_records"] = records
            timing_fields = {
                "calendar_source_sha256": "school_calendar",
                "operation_schedule_source_sha256": "school_operation_time",
                "class_schedule_source_sha256": "class_hours",
                "local_clock_source_sha256": "local_clock",
                "beacon_configuration_source_sha256": "beacon_configuration",
                "beacon_state_source_sha256": "beacon_state",
                "sign_instruction_source_sha256": "sign_instruction",
            }
            for field, source in timing_fields.items():
                packet["timing_packet"][field] = records[source]["sha256"]
            site = root / "site.json"
            site.write_text(json.dumps(packet) + "\n")
            loaded = validate_site(site, packet["case_id"])
            self.assertEqual(loaded["_source_sha256"], hashlib.sha256(site.read_bytes()).hexdigest())
            (root / "beacon_state.txt").write_text("changed diagnostic readback\n")
            with self.assertRaisesRegex(ValueError, "reviewed source hash differs: beacon_state"):
                validate_site(site, packet["case_id"])

    def test_exact_case_and_plan_static_check(self):
        from runner import check
        self.assertEqual(check()["case_id"], ASSIGNMENT + "__children_active_zone")
