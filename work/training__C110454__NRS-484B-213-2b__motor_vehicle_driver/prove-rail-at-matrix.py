"""Bind all four exact-100-foot draft chains to the current source-hashed manifest."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
from camera_lifecycle_audit import audit as camera_audit  # noqa: E402
from worker_exchange.candidate_constructions import validate  # noqa: E402


def read(path: Path):
    return json.loads(path.read_text())


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest_path = HERE / "draft-rail-at-execution-manifest.json"
manifest = read(manifest_path)
assert manifest["status"] == "draft_unselected_rail_at_boundary"
assert len(manifest["cases"]) == 1
entry = manifest["cases"][0]
case_id = HERE.name + "__rail_at"
assert entry["case_id"] == case_id
shape = validate(HERE, entry, "NRS-484B-213-2b", "C110454",
                 required=False, require_alternate=True, candidate_count=4)
assert shape["fallbacks"] == ["fallback1", "fallback2", "fallback3"]
manifest_sha = sha(manifest_path)
results = []
for ident, candidate in [("primary", entry), *[(c["id"], c) for c in entry["candidates"]]]:
    construction = HERE / candidate["construction"]
    assert sha(construction) == candidate["construction_sha256"]
    log_paths = {name: HERE / f"update034-rail-at-{ident}-{name}.log"
                 for name in ("offline", "compatibility", "saved")}
    logs = {name: read(path) for name, path in log_paths.items()}
    assert logs["offline"]["offline_passed"] is True
    assert logs["compatibility"]["passed"] is True
    assert logs["compatibility"]["construction_sha256"] == candidate["construction_sha256"]
    assert logs["compatibility"]["negative_removed"] == "statutory_context.json"
    assert "negative_case_source" in logs["compatibility"]["checks"]
    assert logs["saved"]["passed"] is True and logs["saved"]["recorded_only"] is True
    assert logs["saved"]["originals_preserved"] is True
    assert logs["saved"]["missing_evidence"] is False
    assert logs["saved"]["physical_acceptance_claimed"] is False
    assert logs["saved"]["legal_acceptance_claimed"] is False
    assert all(logs[name]["candidate_id"] == ident for name in logs)
    attempt = ROOT / ".runtime-work" / f"c110454-rail-at-{ident}-compat-034"
    offline = ROOT / ".runtime-work" / f"c110454-rail-at-{ident}-offline-034"
    assert read(attempt / "candidate-selection.json")["manifest_sha256"] == manifest_sha
    assert read(offline / "candidate-selection.json")["manifest_sha256"] == manifest_sha
    assert read(attempt / "candidate-selection.json")["construction_sha256"] == candidate["construction_sha256"]
    audit = camera_audit(attempt, log_paths["saved"], case_id, ident,
                         candidate["construction_sha256"], diagnostic=True)
    assert audit["camera_source_shape_passed"] is True and audit["passed"] is False
    results.append({"candidate_id": ident, "construction_sha256": candidate["construction_sha256"],
                    "logs": {name: {"path": path.name, "sha256": sha(path)} for name, path in log_paths.items()},
                    "camera_source_shape_passed": True, "original_native_accepted": False})
proof = {"format": "c110454-rail-at-draft-matrix-v1", "case_id": case_id,
         "manifest_sha256": manifest_sha, "candidate_count": 4,
         "results": results, "selected": False, "physical_acceptance_claimed": False}
out = HERE / "update034-rail-at-matrix-proof.json"
out.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps({"case_id": case_id, "candidate_count": len(results),
                  "manifest_sha256": manifest_sha, "proof_sha256": sha(out)}))
