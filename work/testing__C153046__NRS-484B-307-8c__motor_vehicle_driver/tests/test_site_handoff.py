"""The canonical Native capture receives only a sealed reviewed site packet."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import resolve_site_packet
from source_bound_scene import sha
from tests.test_source_bound_scene import fixture


class SiteHandoffTests(unittest.TestCase):
    def test_env_packet_staged_for_fresh_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, attempt = root / "reviewed", root / "attempt"
            source.mkdir()
            attempt.mkdir()
            packet = source / "site.json"
            packet.write_text(json.dumps(fixture(source)) + "\n")
            (attempt / "config.json").write_text(json.dumps({
                "selected_case_id": (
                    "testing__C153046__NRS-484B-307-8c__motor_vehicle_driver"
                    "__stopped_leftmost_clear"
                )
            }) + "\n")
            with patch.dict(os.environ, {
                "C153046_SITE_PACKET": str(packet),
                "C153046_SITE_PACKET_SHA256": sha(packet),
            }):
                staged = resolve_site_packet(attempt)
                self.assertEqual(staged, (attempt / "site.json").resolve())
                self.assertEqual(staged.read_bytes(), packet.read_bytes())
                for descriptor in json.loads(packet.read_text())["sources"].values():
                    self.assertEqual(
                        (attempt / descriptor["path"]).read_bytes(),
                        (source / descriptor["path"]).read_bytes(),
                    )
                with self.assertRaisesRegex(ValueError, "retained site packet"):
                    resolve_site_packet(attempt)

    def test_missing_and_changed_packet_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, attempt = root / "reviewed", root / "attempt"
            source.mkdir()
            attempt.mkdir()
            packet = source / "site.json"
            packet.write_text(json.dumps(fixture(source)) + "\n")
            (attempt / "config.json").write_text(json.dumps({
                "selected_case_id": (
                    "testing__C153046__NRS-484B-307-8c__motor_vehicle_driver"
                    "__stopped_leftmost_clear"
                )
            }) + "\n")
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ValueError, "C153046_SITE_PACKET"):
                    resolve_site_packet(attempt)
            with patch.dict(os.environ, {
                "C153046_SITE_PACKET": str(packet),
                "C153046_SITE_PACKET_SHA256": "0" * 64,
            }):
                with self.assertRaisesRegex(ValueError, "SHA-256 missing or changed"):
                    resolve_site_packet(attempt)
            self.assertFalse((attempt / "site.json").exists())


if __name__ == "__main__":
    unittest.main()
