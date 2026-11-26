"""Exercise the public recipe materializer and exact saved measurement contract."""

import json
import os
from pathlib import Path
import shutil
import sys

from worker_exchange.fixture_recipe import materialize
from worker_exchange.measurement_contract import validate, verify_report

from finalize import finalize


ROOT = Path(__file__).resolve().parent
FOLDER = ROOT.parent
REPO = FOLDER.parents[1]


def run():
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) / "fixture-contract-proof"
    scratch.mkdir(parents=True, exist_ok=True)
    contract = json.loads((ROOT / "selected-measurement-contract.json").read_text())
    plan = json.loads((FOLDER / "case-plan.json").read_text())
    positives, negatives = [], []
    for number in (1, 2, 3, 4):
        case = FOLDER.name + "__probe_" + str(number)
        target = scratch / ("probe-" + str(number))
        if target.exists():
            shutil.rmtree(target)
        source = materialize(REPO, ROOT / ("probe-" + str(number) + "-fixture-recipe.json"), target)
        construction = json.loads((ROOT / ("probe-" + str(number) + "-construction.json")).read_text())
        for item in construction["files"]:
            path = target / item["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(item["content"])
        (target / "finalize.py").write_text((ROOT / "finalize.py").read_text())
        validate(contract, plan["requirement_dispositions"],
                 (ROOT / "finalize.py").read_text(), case)
        report = finalize(target, target / "analysis-report.json")
        measurements = verify_report(contract, report, target)
        assert report["case_id"] == case and not report["physical_acceptance_claimed"]
        assert not report["legal_verdict_claimed"]
        positives.append({"case_id": case, "fixture_sha256": source["fixture_sha256"],
                          "measurement_keys": sorted(measurements),
                          "open_duration_s": report["measured"]["open_duration_s"]})
        (target / "result.json").unlink()
        (target / "original-scene-review.json").unlink()
        try:
            finalize(target, target / "missing-source-report.json")
        except ValueError as error:
            assert "Missing required source: original-scene-review.json" in str(error)
            negatives.append(case)
        else:
            raise AssertionError("Missing scene source accepted")
    return {"format": "c228817-public-recipe-measurement-proof-v1",
            "diagnostic_only": True, "positives": positives,
            "missing_case_source_rejected": negatives}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
