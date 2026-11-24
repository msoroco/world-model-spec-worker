"""Materialize a hash-bound FFV1 diagnostic and execute saved analysis."""
import json
import sys
import tempfile
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.fixture_recipe import materialize
from worker_exchange.measurement_contract import verify_report
from worker_exchange.media import audit
from finalizer import finalize

with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c158208-diagnostic-") as tmp:
    attempt = Path(tmp) / "attempt"
    source = materialize(REPO, PACKAGE / "diagnostic-recipe.json", attempt)
    config = json.loads((PACKAGE / "config.json").read_text())
    config["selected_case_id"] = "testing__C158208__NRS-484B-257-2__motor_vehicle_driver__yield_other_inside"
    (attempt / "config.json").write_text(json.dumps(config))
    result = finalize(attempt, attempt / "analysis-report.json")
    contract = json.loads((PACKAGE / "measurement-contract.json").read_text())
    checked = verify_report(contract, json.loads((attempt / "analysis-report.json").read_text()), attempt)
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        audit(attempt / (name + ".mkv"), 3)
    if len(checked) != 6 or result["physical_acceptance_claimed"]:
        raise ValueError("Diagnostic analysis or provenance differs")
    print("ffv1-diagnostic-saved-analysis-passed", source["fixture_sha256"], len(checked))
    negative = Path(tmp) / "negative"
    materialize(REPO, PACKAGE / "diagnostic-recipe.json", negative)
    (negative / "config.json").write_text(json.dumps(config))
    (negative / "entry_history.jsonl").unlink()
    try:
        finalize(negative, negative / "analysis-report.json")
    except ValueError as exc:
        if "Missing required source: entry_history.jsonl" not in str(exc):
            raise
        print("ffv1-diagnostic-missing-entry-history-rejected")
    else:
        raise ValueError("Missing diagnostic entry history was accepted")
