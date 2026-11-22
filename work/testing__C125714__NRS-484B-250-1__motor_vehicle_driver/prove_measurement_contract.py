"""Check the selected witness measurement against generated source bytes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove(proof_root):
    output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
    if not output_root or REPO / ".runtime-work" not in Path(output_root).resolve().parents:
        raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    sys.path.insert(0, str(REPO / "runtime" / "scenario_pipeline"))
    from worker_exchange.measurement_contract import validate, verify_report

    proof = Path(proof_root).resolve() / "precedence"
    fixture = proof / "fixture"
    report_path = proof / "positive" / "analysis-report.json"
    negative_log = proof / "negative.log"
    contract_path = ROOT / "measurement-contract.json"
    plan = json.loads((ROOT / "case-plan.json").read_text())
    contract = json.loads(contract_path.read_text())
    rows = validate(contract, plan["requirement_dispositions"],
                    (ROOT / "analysis.py").read_text(), ROOT.name + "__precedence")
    values = verify_report(contract, json.loads(report_path.read_text()), fixture)
    expected = contract["negative"]["error_contains"]
    if expected not in negative_log.read_text():
        raise ValueError("Negative saved proof omitted the required source failure")
    item = values["crossing_entry_measurement"]
    if item["value"]["other_entered_before_ego"] is not True:
        raise ValueError("Selected witness entry order not measured")
    receipt = {"format": "worker-measurement-diagnostic-proof",
               "case_id": ROOT.name + "__precedence", "diagnostic_only": True,
               "selected_rows": len(rows), "measurement_keys": sorted(values),
               "measurement_contract_sha256": sha(contract_path),
               "analysis_sha256": sha(ROOT / "analysis.py"),
               "report_sha256": sha(report_path),
               "negative_log_sha256": sha(negative_log),
               "negative_error_contains": expected,
               "source_hashes": item["sources"],
               "legal_judgment": "unresolved", "physical_acceptance_claimed": False}
    (ROOT / "measurement-diagnostic-proof.json").write_text(
        json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof-root", required=True)
    print(json.dumps(prove(parser.parse_args().proof_root)))
