"""Independently rebind selected delivery receipts, risks, and draft queue."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "runtime/pipeline/scenario_pipeline"))
from worker_exchange.delivery_handoff import validate_case


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


manifest = json.loads((ROOT / "execution-manifest.json").read_text())
queue = json.loads((ROOT / "update015-delivery-queue-draft.json").read_text())
proof = json.loads((ROOT / "update015-delivery-auditor-cpu-proof.json").read_text())
expected = {entry["case_id"] for entry in manifest["cases"]}
if expected != {row["case_id"] for row in queue["cases"]} or len(expected) != 4:
    raise ValueError("Draft queue case set differs")
if proof.get("canonical_delivery_audits") != 0 or proof.get("accepted_recordings") != 0:
    raise ValueError("Synthetic auditor proof claims acceptance")
risks = {}
for entry in manifest["cases"]:
    validate_case(ROOT, entry, ["full-train"])
    case = entry["case_id"]
    row = next(item for item in queue["cases"] if item["case_id"] == case)
    if not all(case in row[key] for key in (
            "prepare_command", "execute_command", "accept_command",
            "additional_source_audit_command", "postprocessing_command")):
        raise ValueError("Exact case absent from drafted command")
    candidates = entry["candidates"]
    if {item["id"] for item in candidates} != set(row["candidate_commands"]):
        raise ValueError("Draft queue omits fallback")
    metrics = [item["trigger"]["metric"] for item in candidates]
    if len(metrics) != len(set(metrics)):
        raise ValueError("Fallback physical-risk triggers are not distinct")
    if ([item["changed_knobs"] for item in candidates] !=
            [["requested_approach_speed_mps"], ["camera_policy"], ["pre_turn_dwell_s"]]):
        raise ValueError("Fallback risk no longer matches its changed construction knob")
    risks[case] = metrics

result = {"format": "c111662-delivery-contract-audit-v1", "passed": True,
          "selected_cases": len(expected), "fallbacks_checked": len(expected) * 3,
          "draft_queue_cases": len(queue["cases"]),
          "draft_queue_comparisons": len(queue["comparison_audit_commands"]),
          "manifest_sha256": sha(ROOT / "execution-manifest.json"),
          "auditor_proof_sha256": sha(ROOT / "update015-delivery-auditor-cpu-proof.json"),
          "draft_queue_sha256": sha(ROOT / "update015-delivery-queue-draft.json"),
          "risk_metrics": risks,
          "canonical_delivery_audits": 0, "accepted_recordings": 0,
          "batch_queue_complete": False, "integration_proved": False}
output = ROOT / "update015-delivery-contract-audit.json"
output.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"passed": True, "selected_cases": len(expected),
                  "sha256": sha(output)}))
