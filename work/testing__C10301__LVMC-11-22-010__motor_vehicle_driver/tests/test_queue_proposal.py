"""Check provisional dispatch syntax and fail-closed saved-source auditing."""
from __future__ import annotations

import json
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import patch

import build_queue_proposal
import source_audit_cli


class QueueProposalTests(unittest.TestCase):
    def test_exact_cases_and_cli_order(self):
        proposal = build_queue_proposal.build()
        assignment = build_queue_proposal.ASSIGNMENT
        self.assertEqual(proposal["status"], "partial_attention_sweep_source_pending")
        self.assertEqual(len(proposal["cases"]), 2)
        self.assertEqual(len(proposal["comparison_audit_commands"]), 1)
        for row in proposal["cases"]:
            self.assertEqual(row["assignment_id"], assignment)
            self.assertEqual(row["candidate_commands"], {})
            for key, subcommand in (("prepare_command", "prepare-delivery"),
                                    ("execute_command", "execute-delivery"),
                                    ("accept_command", "accept-delivery")):
                tokens = shlex.split(row[key])
                self.assertLess(tokens.index("--root"), tokens.index(subcommand))
                self.assertEqual(tokens[tokens.index("--case") + 1], row["case_id"])
            self.assertIn("--review-archive /external/archive", row["accept_command"])
            self.assertNotIn(" --case ", row["owner_release_command"])
            self.assertIn(row["case_id"], row["additional_source_audit_command"])

    def test_source_audit_rejects_diagnostic_before_receipt(self):
        case = build_queue_proposal.ASSIGNMENT + "__steady_travel"
        scratch = build_queue_proposal.HERE.parents[1] / ".runtime-work" / "c10301-queue-test"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            output = Path(directory) / "receipt.json"
            with patch.object(source_audit_cli, "audit", return_value={
                    "case_id": case, "diagnostic_fixture": True,
                    "decoded_original_pngs": 3600}):
                with self.assertRaisesRegex(ValueError, "diagnostic source"):
                    source_audit_cli.main(["--case", case, "--attempt", directory,
                                           "--output", str(output)])
            self.assertFalse(output.exists())
            with patch.object(source_audit_cli, "audit", return_value={
                    "case_id": case, "diagnostic_fixture": False,
                    "decoded_original_pngs": 3600}):
                self.assertEqual(source_audit_cli.main([
                    "--case", case, "--attempt", directory,
                    "--output", str(output)]), 0)
            self.assertFalse(json.loads(output.read_text())["diagnostic_fixture"])


if __name__ == "__main__":
    unittest.main()
