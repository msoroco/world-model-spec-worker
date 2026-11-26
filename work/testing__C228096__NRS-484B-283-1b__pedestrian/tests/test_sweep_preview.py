"""Verify the pinned expander accepts the bounded engineering preview."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
sys.path.insert(0, str(PACKAGE))

from build_sweep_preview import preview


class SweepPreviewTests(unittest.TestCase):
    def test_pinned_expansion_has_six_bounded_new_cases(self):
        scratch = REPO / ".runtime-work" / "c228096-owner"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="sweep-expand-", dir=scratch) as temporary:
            folder = Path(temporary)
            proposal = folder / "proposal.json"
            templates = folder / "templates.json"
            expanded = folder / "expanded.json"
            proposal.write_text(json.dumps(preview()) + "\n", encoding="utf-8")
            templates.write_text(json.dumps([json.loads(
                (PACKAGE / "proposals/template.json").read_text())]) + "\n", encoding="utf-8")
            env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(folder),
                       TMPDIR=str(folder), PYTHONDONTWRITEBYTECODE="1")
            command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
                       "expand", "--proposal", str(proposal), "--templates", str(templates),
                       "--bindings", str(PACKAGE / "proposals/bindings.json"),
                       "--output", str(expanded)]
            done = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            value = json.loads(expanded.read_text(encoding="utf-8"))
            self.assertTrue(value["sweeps_expanded"])
            self.assertEqual(len(value["cases"]), 12)
            self.assertEqual([s["planned_case_count"] for s in value["sweep_specs"]], [3, 3])
            actual = {c["sweep_id"].rsplit("__", 1)[-1]: set() for c in value["cases"]
                      if c.get("sweep_id")}
            for case in value["cases"]:
                if case.get("sweep_id"):
                    actual[case["sweep_id"].rsplit("__", 1)[-1]].add(
                        next(iter(case["sweep_point"].values())))
            self.assertEqual(actual["sudden_departure"], {4.0, 6.0, 8.0})
            self.assertEqual(actual["yield_impossibility"], {10.0, 20.0, 30.0})
            self.assertEqual(len({c["case_id"] for c in value["cases"]}), 12)


if __name__ == "__main__":
    unittest.main()
