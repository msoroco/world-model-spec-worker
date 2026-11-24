"""Replay pinned canonical selected-manifest and package receipt CPU checks."""

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.execution_manifest import validate  # noqa: E402
from worker_exchange.package_compatibility import check_receipts  # noqa: E402


selected = ROOT / "selected-v2-manifest.json"
canonical = ROOT / "execution-manifest.json"
assert selected.read_bytes() == canonical.read_bytes()
manifest = validate(REPO, ROOT.name)
assert check_receipts(REPO, ROOT, manifest)
print(json.dumps({"format": "c131364-canonical-selected-cpu-proof",
                  "passed": True,
                  "selected_manifest_sha256": hashlib.sha256(selected.read_bytes()).hexdigest(),
                  "canonical_manifest_sha256": hashlib.sha256(canonical.read_bytes()).hexdigest(),
                  "selected_case_ids": manifest["selected_case_ids"],
                  "package_compatibility_case_count": len(manifest["cases"]),
                  "physical_acceptance_claimed": False}))
