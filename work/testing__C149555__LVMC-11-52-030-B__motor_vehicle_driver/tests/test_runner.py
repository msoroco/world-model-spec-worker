"""Native entrypoint exact identity and external original-source gate."""

import json
import tempfile
import unittest
from pathlib import Path

from freight_contract import SourceError
from runner import check, copy_original_sources


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


if __name__ == "__main__":
    unittest.main()
