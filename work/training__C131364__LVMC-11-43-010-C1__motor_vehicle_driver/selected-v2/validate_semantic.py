"""Replay the pinned canonical semantic stage validator on selected cases."""

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.semantic_delivery import validate  # noqa: E402


assignment_path = REPO / "inputs" / ROOT.name / "assignment.json"
manifest_path = ROOT / "selected-v2-manifest.json"
assignment = json.loads(assignment_path.read_text())
manifest = json.loads(manifest_path.read_text())
result = validate(ROOT, assignment, manifest)
print(json.dumps({
    "format": "c131364-selected-semantic-cpu-proof",
    "passed": True,
    "assignment_sha256": hashlib.sha256(assignment_path.read_bytes()).hexdigest(),
    "selected_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    **result,
    "physical_acceptance_claimed": False,
}))
