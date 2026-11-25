"""Native entrypoint exact identity and external original-source gate."""

import json
import tempfile
import unittest
from pathlib import Path

from freight_contract import SourceError
from runner import check, copy_original_sources, write_delivery_manifest, sha


class RunnerTests(unittest.TestCase):
    def test_exact_six_case_configuration(self):
        config = check()
        self.assertEqual(len(config["supported_case_ids"]), 6)
        self.assertEqual(config["frame_count"], 900)

    def test_diagnostic_source_cannot_replace_reviewed_originals(self):
        scratch = Path.cwd() / ".runtime-work" / "c149555-runner-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            source = root / "source"
            attempt = root / "attempt"
            source.mkdir()
            attempt.mkdir()
            (source / "fixture.json").write_text(json.dumps({"diagnostic_fixture": True}) + "\n")
            with self.assertRaises(SourceError):
                copy_original_sources(source,
                                      {"sources": {"diagnostic_fixture": {"path": "fixture.json"}}},
                                      attempt, case_id=check()["selected_case_id"])

    def test_delivery_manifest_seals_canonical_result_and_four_media(self):
        scratch = Path.cwd() / ".runtime-work" / "c149555-runner-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            attempt = Path(temporary)
            canonical = attempt / "result.json"
            canonical.write_text("{}\n", encoding="utf-8")
            media = {}
            for name in ("overview", "approach", "reference_corner", "driver_reference"):
                path = attempt / (name + ".mkv")
                path.write_bytes(name.encode())
                media[name] = {"path": path.name, "sha256": sha(path)}
            source = {"case_id": check()["selected_case_id"], "kind": "delivery",
                      "acquisition_kind": "original_native",
                      "sources": {"native_result": {"path": "freight-native-source.json",
                                                     "sha256": "source-seal"}}}
            inventory = {"job_id": "job-1", "attempt_id": "attempt-1",
                         "recording_id": "recording-1"}
            written = write_delivery_manifest(attempt, source, media, canonical, inventory)
            value = json.loads(written.read_text(encoding="utf-8"))
            self.assertEqual(value["canonical_result_sha256"], sha(canonical))
            self.assertEqual(value["native_result_sha256"], "source-seal")
            self.assertFalse(value["diagnostic_fixture"])
            self.assertEqual(set(value["media"]), set(media))
            (attempt / "overview.mkv").write_bytes(b"tampered")
            with self.assertRaises(SourceError):
                write_delivery_manifest(attempt, source, media, canonical, inventory)


if __name__ == "__main__":
    unittest.main()
