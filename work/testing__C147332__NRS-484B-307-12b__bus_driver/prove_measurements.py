"""Run pinned measurement contract and missing-source negatives on exact cases."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from analysis import build_report
from bus_route import ROUTES
from test_comparison_audit import make_attempt
from worker_exchange.measurement_contract import validate, verify_report


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name


def main():
    output_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if not output_root.is_relative_to((REPO / ".runtime-work").resolve()):
        raise ValueError("runtime output root must stay under .runtime-work")
    output = REPO / ".runtime-work" / "c147332-measurement-v3"
    if output.exists():
        raise ValueError("retain prior measurement fixture; use a new proof root")
    output.mkdir(parents=True)
    plan = json.loads((ROOT / "case-plan.json").read_text())
    analysis_code = (ROOT / "analysis.py").read_text()
    for kind in ROUTES:
        case_id = ASSIGNMENT + "__" + kind
        attempt = output / kind
        make_attempt(attempt, kind)
        contract = json.loads((ROOT / "cases" / kind / "measurement-contract.json").read_text())
        validate(contract, plan["requirement_dispositions"], analysis_code, case_id)
        selected = verify_report(contract, build_report(attempt), attempt)
        negative = output / (kind + "-negative")
        shutil.copytree(attempt, negative)
        (negative / "lane-signal-history.jsonl").unlink()
        try:
            build_report(negative)
        except ValueError as error:
            if str(error) != contract["negative"]["error_contains"]:
                raise
        else:
            raise AssertionError("missing original signal source was accepted")
        print(json.dumps({"case_id": case_id, "selected_measurements": sorted(selected),
                          "missing_signal_rejected": True,
                          "diagnostic_fixture_only": True}))


if __name__ == "__main__":
    main()
