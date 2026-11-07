"""Pinned positive and negative saved measurement-contract diagnostics."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "runtime/pipeline/scenario_pipeline"), str(HERE / "native")]
from worker_exchange.measurement_contract import validate, verify_report
from finalize import finalize


def run() -> dict:
    plan = json.loads((HERE / "case-plan.json").read_text())
    code = (HERE / "native/finalize.py").read_text()
    out = []
    for case, name in zip(plan["cases"], ("decrease", "hold")):
        suffix = case["case_id"].split("__")[-1]
        contract = json.loads((HERE / f"draft-measurement-contract-{suffix}.json").read_text())
        validate(contract, plan["requirement_dispositions"], code, case["case_id"])
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work", prefix="c111294-603-contract-") as scratch:
            fixture = Path(scratch)
            source = HERE / "draft-fixtures" / f"{name}-synthetic-native.jsonl"
            shutil.copyfile(source, fixture / "native_samples.jsonl")
            shutil.copyfile(HERE / "draft-fixtures/road.xodr", fixture / "road.xodr")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            report = finalize(fixture, contract, digest)
            verify_report(contract, report, fixture)
            if report["measurements"]["intersection_approach"]["value"]["measured_relation"] != (
                    "measured_early_decrease_held" if name == "decrease" else "measured_no_material_decrease"):
                raise AssertionError("Controlled measurement relation differs")
            try:
                finalize(fixture, contract, "0"*64)
            except ValueError as exc:
                if str(exc) != "Saved Native source hash changed":
                    raise
            else:
                raise AssertionError("Changed source hash accepted")
            (fixture / "native_samples.jsonl").unlink()
            try:
                finalize(fixture, contract, digest)
            except ValueError as exc:
                if str(exc) != contract["negative"]["error_contains"]:
                    raise
            else:
                raise AssertionError("Missing source accepted")
            out.append({"case_id": case["case_id"], "source_sha256": digest,
                        "relation": report["measurements"]["intersection_approach"]["value"]["measured_relation"],
                        "positive": True, "negative_missing_source": True,
                        "negative_changed_source": True})
    return {"passed": True, "cases": out, "selected": False,
            "physical_observations": 0, "legal_verdicts": 0}


if __name__ == "__main__":
    result = run()
    (HERE / "measurement-contract-proof.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, sort_keys=True))
