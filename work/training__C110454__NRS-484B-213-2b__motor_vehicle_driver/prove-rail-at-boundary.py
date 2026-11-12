"""Verify the unselected at-100-foot candidate sources and retained offline logs."""
from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
from worker_exchange.candidate_constructions import validate  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest_path = HERE / "draft-rail-at-execution-manifest.json"
manifest = json.loads(manifest_path.read_text())
assert manifest["status"] == "draft_unselected_rail_at_boundary"
assert len(manifest["cases"]) == 1
entry = manifest["cases"][0]
assert entry["case_id"] == HERE.name + "__rail_at"
result = validate(HERE, entry, "NRS-484B-213-2b", "C110454",
                  required=False, require_alternate=True, candidate_count=4)
assert result["fallbacks"] == ["fallback1", "fallback2", "fallback3"]
sources = {"primary": entry, **{c["id"]: c for c in entry["candidates"]}}
logs = {}
for ident, source in sources.items():
    assert sha(HERE / source["construction"]) == source["construction_sha256"]
    path = HERE / f"update033-rail-at-{ident}-offline.log"
    assert '"offline_passed": true' in path.read_text(), ident
    logs[ident] = {"log": path.name, "sha256": sha(path), "construction_sha256": source["construction_sha256"]}
bad = deepcopy(entry)
bad["candidates"][0]["construction_sha256"] = "0" * 64
try:
    validate(HERE, bad, "NRS-484B-213-2b", "C110454",
             required=False, require_alternate=True, candidate_count=4)
except ValueError as exc:
    assert "Fallback construction changed" in str(exc), str(exc)
else:
    raise AssertionError("Tampered fallback source hash was accepted")
proof = {
    "format": "c110454-rail-at-draft-offline-v1",
    "case_id": entry["case_id"], "selected": False, "native_capture_claimed": False,
    "manifest": manifest_path.name, "manifest_sha256": sha(manifest_path),
    "validation": result, "candidate_offline": logs,
    "negative_rejection": "changed fallback construction SHA-256",
    "geometry": "Authored sampled full-body nearest-front distance is 30.48 m at railroad crossing; original Native measurement remains unobserved",
}
out = HERE / "update033-rail-at-offline-proof.json"
out.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof, indent=2))
