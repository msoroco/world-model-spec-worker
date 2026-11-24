"""Validate exact selected measurement rows against the active runtime contract."""
import json
import sys
import tempfile
import hashlib
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.measurement_contract import validate, verify_report
from finalizer import bound_measurements
from yield_entry_measurements import analyze
from tests.test_yield_entry import YieldEntryTests

plan = json.loads((PACKAGE / "case-plan.json").read_text())
contract = json.loads((PACKAGE / "measurement-contract.json").read_text())
officer_contract = json.loads((PACKAGE / "measurement-contract-officer.json").read_text())
code = (PACKAGE / "finalizer.py").read_text()
for case in plan["cases"]:
    selected = officer_contract if case["case_id"].endswith("__officer_control_exception") else contract
    rows = validate(selected, plan["requirement_dispositions"], code, case["case_id"])
    print(case["case_id"], len(rows))

with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c158208-measurement-") as tmp:
    fixture = Path(tmp)
    YieldEntryTests().fixture(fixture)
    values = bound_measurements(analyze(fixture))
    checked = verify_report(contract, {"measurements": values}, fixture)
    if set(checked) != {row["output_key"] for row in contract["requirements"]}:
        raise ValueError("Selected measurement keys differ")
    print("source-hash-bound-positive", len(checked))
    (fixture / "entry_history.jsonl").write_text("altered source\n")
    try:
        verify_report(contract, {"measurements": values}, fixture)
    except ValueError as exc:
        if "source hash differs" not in str(exc):
            raise
        print("changed-source-rejected")
    else:
        raise ValueError("Changed diagnostic source was accepted")

with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c158208-officer-") as tmp:
    fixture = Path(tmp)
    YieldEntryTests().fixture(fixture)
    context_path = fixture / "intersection_context.json"
    context = json.loads(context_path.read_text())
    context["case_id"] = next(c["case_id"] for c in plan["cases"]
                              if c["case_id"].endswith("__officer_control_exception"))
    context["police_control"] = True
    context_path.write_text(json.dumps(context))
    review_path = fixture / "site_review.json"
    review = json.loads(review_path.read_text())
    review["intersection_context_sha256"] = hashlib.sha256(context_path.read_bytes()).hexdigest()
    review_path.write_text(json.dumps(review))
    officer_path = fixture / "officer_review.json"
    officer_path.write_text(json.dumps({"intersection_context_sha256": review["intersection_context_sha256"],
        "camera_sha256": review["camera_sha256"], "reviewed_carla_frames": [100, 101, 102],
        "officer_actor_id": 99, "control_observed_at_entry": True,
        "authority_judgment": "unresolved"}))
    values = bound_measurements(analyze(fixture))
    verify_report(officer_contract, {"measurements": values}, fixture)
    print("officer-review-source-bound-positive")
    officer_path.write_text(officer_path.read_text() + "\n")
    try:
        verify_report(officer_contract, {"measurements": values}, fixture)
    except ValueError as exc:
        if "source hash differs" not in str(exc):
            raise
        print("changed-officer-review-rejected")
    else:
        raise ValueError("Changed officer source was accepted")
