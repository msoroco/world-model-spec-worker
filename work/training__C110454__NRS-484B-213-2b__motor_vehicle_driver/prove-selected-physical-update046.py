"""Verify current graph motion fixtures and selected manifest bindings."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ATTEMPTS = ROOT / ".runtime-work/c110454-update044-nine-selected"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest_path = HERE / "execution-manifest.json"
manifest = read(manifest_path)
rows = []
assert len(manifest["cases"]) == 9
for entry in manifest["cases"]:
    case = entry["case_id"]
    suffix = case.removeprefix(HERE.name + "__")
    spec = entry["physical_preparation"]
    proof_path = HERE / spec["receipt"]
    assert sha(proof_path) == spec["sha256"]
    proof = read(proof_path)
    assert proof["case_id"] == case and proof["construction_sha256"] == entry["construction_sha256"]
    assert proof["fixtures_are_cpu_mocks"] and proof["original_native_motion_verified"] is False
    assert {fixture["kind"] for fixture in proof["fixtures"]} == {
        "complete_motion", "incomplete_motion", "missing_evidence"}
    for fixture in proof["fixtures"]:
        result_path = HERE / fixture["result"]
        assert sha(result_path) == fixture["result_sha256"]
        assert sha(HERE / fixture["log"]) == fixture["log_sha256"]
        result = read(result_path)
        assert result["provenance_kind"] == "synthetic_fixture"
        assert result["diagnostic_fixture"] is True
        assert result["original_native_motion_verified"] is False
        for name, digest in result["retained_source_sha256"].items():
            assert sha(ATTEMPTS / suffix / "primary/compatibility" / name) == digest
    assert sha(HERE / proof["lifecycle"]["log"]) == proof["lifecycle"]["log_sha256"]
    assert proof["lifecycle"]["exit_code"] == 0
    rows.append({"case_id": case, "receipt": spec["receipt"], "sha256": spec["sha256"]})

index = {"format": "c110454-current-graph-physical-fixtures-v1",
         "manifest_sha256": sha(manifest_path), "selected_cases": len(rows),
         "synthetic_outcome_branches": 3 * len(rows), "lifecycle_fixtures": len(rows),
         "cases": rows, "original_native_motion_verified": False,
         "physical_or_legal_acceptance_claimed": False}
output = HERE / "update046-selected-physical-index.json"
output.write_text(json.dumps(index, indent=2) + "\n")
print(json.dumps({"selected_cases": len(rows), "proof_sha256": sha(output)}))
