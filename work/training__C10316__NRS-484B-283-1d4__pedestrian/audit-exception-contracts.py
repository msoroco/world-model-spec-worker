"""Independently verify the two prior-entry measurement contracts and sources."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
from worker_exchange.measurement_contract import validate, verify_report


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    plan = json.loads((HERE / "case-plan.json").read_text())
    summary = json.loads((HERE / "exception-contract-summary.json").read_text())
    source = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
    assert len(summary["records"]) == 2
    assert plan["requirement_dispositions"][1]["status"] == "selected_required"
    assert plan["requirement_dispositions"][1]["case_ids"] == [
        row["case_id"] for row in summary["records"]]
    assert sha(ROOT / "inputs" / HERE.name / "assignment.json") == plan["sources"][0]["sha256"]
    assert source["law_id"] == plan["law_id"]
    code = (HERE / "native/finalize_exception.py").read_text()
    fixtures = {row["case_id"]: Path(row["retained_positive"])
                for row in json.loads((HERE / "exception-summary.json").read_text())["records"]}
    observed = set()
    for record in summary["records"]:
        case = record["case_id"]
        assert case not in observed
        observed.add(case)
        contract = json.loads((HERE / record["contract"]).read_text())
        assert contract["case_id"] == case
        validate(contract, plan["requirement_dispositions"], code, case)
        assert record["validator_status"] == "passed_selected_measurement_requirement"
        assert record["saved_value_verification"] == "pass"
        assert record["missing_source_negative"] == "pass"
        assert record["lawful_prior_entry_proven"] is False
        assert record["accepted_recording_claimed"] is False
        fixture = fixtures[case]
        context = json.loads((fixture / "exception-context.json").read_text())
        measured = json.loads((fixture / "source-measurement.json").read_text())
        assert context["lawful_prior_entry_review"] == "unverified"
        assert measured["lawful_prior_entry_proven"] is False
        assert measured["as_soon_as_possible_bound_declared"] is False
        assert measured["physical_signal_observed"] is False
        assert measured["progress_bound"]["engineering_surrogate_met"] is True
        assert measured["progress_bound"]["legal_sufficiency_assessed"] is False
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join((str(HERE / "native"), env.get("PYTHONPATH", "")))
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work", prefix="d4-exception-audit-") as tmp:
            output = Path(tmp) / "report.json"
            run = subprocess.run([sys.executable, str(HERE / "native/finalize_exception.py"),
                                  "--attempt", str(fixture), "--output", str(output),
                                  "--case-id", case], env=env, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            assert run.returncode == 0, run.stdout
            report = json.loads(output.read_text())
            verify_report(contract, report, fixture)
            assert report["measurements"]["prior_entry_exception_source_facts"]["sources"] == {
                name: sha(fixture / name) for name in contract["requirements"][0]["inputs"]}
        assert record["entry_indication"] == measured["entry_indication"]
    assert observed == set(plan["requirement_dispositions"][1]["case_ids"])
    print(json.dumps({"passed": True, "contracts": len(observed),
                      "selected_delivery_cases": 0, "lawful_prior_entry_proven": False,
                      "physical_signal_observed": False, "accepted_recordings": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
