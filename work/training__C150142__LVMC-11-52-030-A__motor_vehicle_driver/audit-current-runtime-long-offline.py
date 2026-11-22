"""Check current-runtime binding of all 64 long-case offline receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / "current-runtime-reproof-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    index = json.loads((HERE / "current-runtime-long-offline-index.json").read_text())
    runtime_sha = sha(ROOT / "runtime/pipeline/SOURCE-MANIFEST.json")
    if manifest["runtime_manifest_sha256"] != runtime_sha or index["manifest_sha256"] != sha(manifest_path):
        raise ValueError("Long offline index binds another runtime or manifest")
    expected = {}
    for entry in manifest["cases"]:
        if entry.get("fixture_recipe"):
            continue
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            selected = entry if candidate == "primary" else next(
                row for row in entry["candidates"] if row["id"] == candidate)
            expected[(entry["case_id"], candidate)] = selected["construction_sha256"]
    if len(expected) != 64 or len(index["rows"]) != 64:
        raise ValueError("Expected 16 long cases and 64 candidates")
    seen = set()
    for row in index["rows"]:
        key = row["case_id"], row["candidate_id"]
        log = HERE / row["log"]
        proof = json.loads(log.read_text())
        if key in seen or expected.get(key) != row["construction_sha256"] or \
                sha(log) != row["log_sha256"] or proof.get("offline_passed") is not True or \
                proof.get("simulation_started") is not False or \
                (proof.get("case_id"), proof.get("candidate_id")) != key:
            raise ValueError("Long offline candidate differs: " + str(key))
        seen.add(key)
    if seen != set(expected):
        raise ValueError("Long offline candidate missing")
    print(json.dumps({"long_cases": 16, "exact_candidates": 64,
                      "runtime_manifest_sha256": runtime_sha,
                      "offline_index_sha256": sha(HERE / "current-runtime-long-offline-index.json"),
                      "original_native_observed": False}))


if __name__ == "__main__":
    main()
