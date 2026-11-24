"""Replay pinned exact selected-case delivery contract validation."""

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.delivery_handoff import validate_case  # noqa: E402


manifest_path = ROOT / "selected-v2-manifest.json"
manifest = json.loads(manifest_path.read_text())
validated = []
for case in manifest["cases"]:
    receipt = validate_case(ROOT, case, ["full-train"])
    validated.append({"case_id": case["case_id"],
                      "script_sha256": receipt["script_sha256"],
                      "test_log_sha256": receipt["test_log_sha256"],
                      "negative_log_sha256": receipt["negative_log_sha256"]})
print(json.dumps({"format": "c131364-selected-delivery-contract-cpu-proof",
                  "passed": True,
                  "selected_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                  "validated_cases": validated,
                  "physical_acceptance_claimed": False}))
