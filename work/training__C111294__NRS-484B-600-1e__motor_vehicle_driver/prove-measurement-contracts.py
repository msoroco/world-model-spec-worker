"""Pinned contract positives and negatives on three synthetic saved sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
for parent in ROOT.parents:
    package = parent / "runtime/pipeline/scenario_pipeline"
    if package.is_dir():
        sys.path.insert(0, str(package))
        break
sys.path.insert(0, str(ROOT / "native"))
from worker_exchange.measurement_contract import validate, verify_report
from finalize import finalize


def main() -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    analysis_code = (ROOT / "native/finalize.py").read_text()
    output_root = ROOT / "draft-fixtures/contracts"
    output_root.mkdir(parents=True, exist_ok=True)
    results = {}
    for case in plan["cases"]:
        suffix = case["case_id"].split("__")[-1]
        contract = json.loads((ROOT / f"draft-measurement-contract-{suffix}.json").read_text())
        validate(contract, plan["requirement_dispositions"], analysis_code,
                 case_id=case["case_id"])
        folder = output_root / suffix
        folder.mkdir(exist_ok=True)
        source = folder / "native_samples.jsonl"
        source.write_bytes((ROOT / "draft-fixtures" / f"{suffix}-synthetic-native-samples.jsonl").read_bytes())
        (folder / "road.xodr").write_bytes((ROOT / "draft-fixtures/road.xodr").read_bytes())
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        report = finalize(folder, contract, source_hash)
        verify_report(contract, report, folder)
        (folder / "analysis-report.json").write_text(json.dumps(report, indent=2) + "\n")
        with tempfile.TemporaryDirectory() as temp:
            negative = Path(temp)
            shutil.copy2(folder / "road.xodr", negative / "road.xodr")
            try:
                finalize(negative, contract, source_hash)
            except ValueError as exc:
                if contract["negative"]["error_contains"] not in str(exc):
                    raise
            else:
                raise AssertionError("Missing Native source was accepted")
            changed = bytearray(source.read_bytes())
            changed[100] = (changed[100] + 1) % 256
            (negative / "native_samples.jsonl").write_bytes(changed)
            try:
                finalize(negative, contract, source_hash)
            except ValueError as exc:
                if "hash changed" not in str(exc):
                    raise
            else:
                raise AssertionError("Changed Native source was accepted")
        results[suffix] = {"source_sha256": source_hash,
                           "measurement_keys": sorted(report["measurements"]),
                           "pinned_positive": True,
                           "missing_source_rejected": True,
                           "changed_source_rejected": True}
    summary = {"passed": True, "source_kind": "synthetic_cpu_fixture",
               "selected": False, "portable_compatibility_verified": False,
               "cases": results}
    (output_root / "proof-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
