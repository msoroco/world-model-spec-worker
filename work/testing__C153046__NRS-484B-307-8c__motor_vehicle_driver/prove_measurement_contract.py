"""Prove each exact selected requirement against pinned CPU measurement rules."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
ASSIGNMENT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ASSIGNMENT))

from scenario_pipeline.worker_exchange.measurement_contract import validate, verify_report
from build_case_plan import AID, KINDS
from saved_measurement import finalize_attempt
from tests.test_saved_finalizer import attempt


def main() -> None:
    dispositions = json.loads((ASSIGNMENT / "case-plan.json").read_text())["requirement_dispositions"]
    code = (ASSIGNMENT / "saved_measurement.py").read_text()
    private = ROOT / ".runtime-work" / "c153046-measurement-contract"
    private.mkdir(parents=True, exist_ok=True)
    for suffix in KINDS:
        case_id = AID + "__" + suffix
        contract = json.loads((ASSIGNMENT / "constructions" /
                               (suffix + "-measurement-contract.json")).read_text())
        rows = validate(contract, dispositions, code, case_id)
        if len(rows) != 1:
            raise ValueError("selected legal requirement missing: " + case_id)
        with tempfile.TemporaryDirectory(dir=private) as temporary:
            fixture = Path(temporary)
            if attempt(fixture, suffix=suffix) != case_id:
                raise ValueError("case fixture identity differs")
            report = finalize_attempt(fixture, fixture / "analysis-report.json")
            verified = verify_report(contract, report, fixture)
            observed = verified["red_left_turn_observation"]["value"]
            if observed["case_id"] != case_id or observed["signal_red_frames"] != 13:
                raise ValueError("case-specific Native trace observation differs")
            (fixture / "site.json").unlink()
            try:
                verify_report(contract, report, fixture)
            except FileNotFoundError:
                pass
            else:
                raise ValueError("removed site packet retained a valid measurement")
            with tempfile.TemporaryDirectory(dir=private) as missing:
                missing_root = Path(missing)
                attempt(missing_root, suffix=suffix)
                (missing_root / "site.json").unlink()
                try:
                    finalize_attempt(missing_root, missing_root / "analysis-report.json")
                except ValueError as error:
                    if contract["negative"]["error_contains"] not in str(error):
                        raise
                else:
                    raise ValueError("missing site packet allowed a saved analysis")
        print("pinned selected requirement measurement positive/negative", suffix)


if __name__ == "__main__":
    main()
