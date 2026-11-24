"""Execute the real saved finalizer on a small source-shaped CPU fixture."""
import json
import sys
import tempfile
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from finalizer import finalize
from tests.test_yield_entry import YieldEntryTests

CASE = "testing__C158208__NRS-484B-257-2__motor_vehicle_driver__yield_other_inside"

with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c158208-saved-") as tmp:
    root = Path(tmp)
    YieldEntryTests().fixture(root)
    config = json.loads((PACKAGE / "config.json").read_text())
    config["selected_case_id"] = CASE
    (root / "config.json").write_text(json.dumps(config))
    (root / "trace.jsonl").write_text("".join(json.dumps({"frame": 100 + i,
        "time_s": 1 + i * .05, "position_m": [x, 0, 0], "speed_mps": speed}) + "\n"
        for i, (x, speed) in enumerate(((0, 4), (0, 2), (12, 1)))))
    (root / "capture").mkdir()
    (root / "capture/evidence.jsonl").write_text(json.dumps({
        "source": "synthetic three-frame software diagnostic", "physical_claim": False}) + "\n")
    result = finalize(root, root / "analysis-report.json")
    report = json.loads((root / "analysis-report.json").read_text())
    from worker_exchange.measurement_contract import verify_report
    contract = json.loads((PACKAGE / "measurement-contract.json").read_text())
    values = verify_report(contract, report, root)
    if len(values) != 6 or result["case_id"] != CASE or result["physical_acceptance_claimed"]:
        raise ValueError("Saved diagnostic result scope or acceptance differs")
    if not all(len((root / "channels" / (name + ".jsonl")).read_text().splitlines()) == 3
               for name in ("ego_speed_mps", "other_body_in_intersection", "ego_before_yield_reference")):
        raise ValueError("Saved channels lack original frame coverage")
    print("saved-finalizer-positive", result["case_id"], len(values), result["physical_checks"]["setup"]["status"])

with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c158208-saved-negative-") as tmp:
    root = Path(tmp)
    YieldEntryTests().fixture(root)
    (root / "config.json").write_text((PACKAGE / "config.json").read_text())
    (root / "trace.jsonl").write_text("{}\n")
    (root / "capture").mkdir()
    (root / "capture/evidence.jsonl").write_text("{}\n")
    (root / "entry_history.jsonl").unlink()
    try:
        finalize(root, root / "analysis-report.json")
    except ValueError as exc:
        if "Missing required source: entry_history.jsonl" not in str(exc):
            raise
        print("missing-entry-history-rejected")
    else:
        raise ValueError("Missing entry history was accepted")
