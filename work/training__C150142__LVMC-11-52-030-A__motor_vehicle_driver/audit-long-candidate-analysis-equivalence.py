"""Prove exact saved analysis source identity across all long candidates."""
import copy
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "execution-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analysis_files(construction):
    return {item["path"]: item["content"] for item in construction["files"]
            if item["path"].endswith(".py") and item["path"] != "runner.py"
            and not item["path"].startswith("tests/")}


def require_same(primary, candidate):
    first, second = analysis_files(primary), analysis_files(candidate)
    if first != second:
        changed = sorted(set(first) ^ set(second) |
                         {key for key in set(first) & set(second)
                          if first[key] != second[key]})
        raise ValueError("Saved analysis source differs: " + ",".join(changed))
    return {key: hashlib.sha256(value.encode()).hexdigest()
            for key, value in sorted(first.items())}


def main():
    manifest = json.loads(MANIFEST.read_text())
    rows = []
    for entry in manifest["cases"]:
        primary_path = HERE / entry["construction"]
        primary = json.loads(primary_path.read_text())
        config = json.loads(next(item["content"] for item in primary["files"]
                                 if item["path"] == "config.json"))
        if config.get("capture_frames", 0) <= 2000:
            continue
        contract = json.loads((HERE / entry["measurement_contract"]).read_text())
        removed = "native-passenger-inventory.jsonl" if entry["case_id"].endswith("_no_loading") else "native-passenger-actors.jsonl"
        if contract["negative"] != {"remove": [removed],
                                    "error_contains": "Missing required source: " + removed}:
            raise ValueError("Long negative source guard changed")
        if len(entry["candidates"]) != 3:
            raise ValueError("Expected three retained long fallback candidates")
        for candidate in [{"id": "primary", "construction": entry["construction"],
                           "construction_sha256": entry["construction_sha256"]},
                          *entry["candidates"]]:
            path = HERE / candidate["construction"]
            construction = json.loads(path.read_text())
            if sha(path) != candidate["construction_sha256"]:
                raise ValueError("Candidate construction source changed")
            hashes = require_same(primary, construction)
            if entry["measurement_procedure"]["entrypoint"] not in hashes:
                raise ValueError("Selected finalizer absent from candidate")
            rows.append({"case_id": entry["case_id"],
                         "candidate_id": candidate["id"],
                         "construction_sha256": candidate["construction_sha256"],
                         "negative_removed": removed,
                         "saved_analysis_sha256": hashes})
    if len(rows) != 64 or len({row["case_id"] for row in rows}) != 16:
        raise ValueError("Incomplete long candidate matrix")
    changed = copy.deepcopy(primary)
    finalizer = next(item for item in changed["files"]
                     if item["path"] == "finalize_selected.py")
    finalizer["content"] += "\n# Changed finalizer\n"
    try:
        require_same(primary, changed)
    except ValueError as exc:
        if "finalize_selected.py" not in str(exc):
            raise
    else:
        raise AssertionError("Changed finalizer was accepted")
    print(json.dumps({"format": "c150142-long-candidate-analysis-equivalence-v1",
                      "manifest_sha256": sha(MANIFEST), "runtime_manifest_sha256": manifest["runtime_manifest_sha256"],
                      "rows": rows, "candidate_count": len(rows),
                      "changed_finalizer_rejected": True,
                      "official_public_compatibility_passed": False}, indent=2))


if __name__ == "__main__":
    main()
