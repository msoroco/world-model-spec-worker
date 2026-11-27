"""Run positive and missing-source saved analysis on six synthetic fixtures."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def run() -> None:
    output_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if not output_root.is_relative_to(REPO / ".runtime-work"):
        raise ValueError("runtime output root must be beneath .runtime-work")
    sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
    from worker_exchange.measurement_contract import verify_report

    manifest = json.loads((ROOT / "execution-manifest.draft.json").read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        source = REPO / ".runtime-work/c378245-taxi" / ("diagnostic-" + suffix + "-v1")
        contract = json.loads((ROOT / entry["measurement_contract"]).read_text())
        positive = json.loads((source / "analysis-report.json").read_text())
        verify_report(contract, positive, source)
        folder = ROOT / "cases" / suffix
        positive_log = folder / "saved-analysis-positive.log"
        positive_log.write_text("Exact synthetic taxi case " + entry["case_id"] +
                                ": selected measurements and source hashes passed\n")
        negative = REPO / ".runtime-work/c378245-taxi" / ("negative-" + suffix + "-v1")
        if negative.exists():
            raise ValueError("use fresh negative diagnostic directory")
        shutil.copytree(source, negative)
        (negative / contract["negative"]["remove"][0]).unlink()
        process = subprocess.run([sys.executable, str(ROOT / "analysis.py"),
                                  "--attempt", str(negative),
                                  "--output", str(negative / "analysis-report.json")],
                                 text=True, capture_output=True)
        negative_log = folder / "saved-analysis-negative.log"
        negative_log.write_text((process.stdout + process.stderr).rstrip() + "\n")
        if process.returncode == 0 or contract["negative"]["error_contains"] not in negative_log.read_text():
            raise ValueError("missing activity review source was not rejected: " + suffix)
        print(suffix, "positive and negative source checks passed")


if __name__ == "__main__":
    run()
