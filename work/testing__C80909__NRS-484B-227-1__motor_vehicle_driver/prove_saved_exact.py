"""Repeat saved-only finalization from sealed synthetic source bytes and reject tampering."""
from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
output_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
if not output_root.is_relative_to(REPO / ".runtime-work"):
    raise RuntimeError("SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work")
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from analysis import SOURCES, build_report, saved_result


def main():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    for entry in manifest["cases"]:
        tokens = shlex.split(entry["compatibility"]["command"])
        source = Path(tokens[tokens.index("--output") + 1])
        with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c80909-saved-exact-") as scratch:
            target = Path(scratch)
            for name in (*SOURCES, "acquisition.json", "acquisition-provenance.json",
                         "config.json", "construction.json"):
                shutil.copyfile(source / name, target / name)
            report = build_report(target)
            result = saved_result(target, report)
            if result["diagnostic_fixture"] is not True or result["physical_acceptance_claimed"] is not False:
                raise AssertionError("saved-only fixture was represented as physical acceptance")
            original = target / "observed-vehicle-history.jsonl"
            original.write_text(original.read_text() + "{}\n")
            try:
                build_report(target)
            except ValueError as exc:
                if "stale provenance-bound source" not in str(exc):
                    raise
            else:
                raise AssertionError("changed original other-vehicle history was accepted")
        print(entry["case_id"], "saved-only finalization and changed-source rejection passed")


if __name__ == "__main__":
    main()
