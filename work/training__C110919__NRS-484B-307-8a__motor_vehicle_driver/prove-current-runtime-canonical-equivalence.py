"""Prove the current reproof harness retains all selected case constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text())

def main():
    canonical = HERE / "execution-manifest.json"
    harness = HERE / "current-runtime-reproof-manifest.json"
    old, new = read(canonical), read(harness)
    runtime = sha(ROOT / "runtime/pipeline/SOURCE-MANIFEST.json")
    if new["runtime_manifest_sha256"] != runtime:
        raise ValueError("Current runtime differs")
    a, b = old["cases"], new["cases"]
    if len(a) != 20 or len(b) != 20:
        raise ValueError("Twenty exact selected cases required")
    rows = []
    for original, current in zip(a, b):
        if original["case_id"] != current["case_id"]:
            raise ValueError("Selected case identity differs")
        old_hashes = [original["construction_sha256"]] + [
            x["construction_sha256"] for x in original["candidates"]]
        new_hashes = [current["construction_sha256"]] + [
            x["construction_sha256"] for x in current["candidates"]]
        if old_hashes != new_hashes:
            raise ValueError("Selected construction changed")
        for candidate in [current, *current["candidates"]]:
            if sha(HERE / candidate["construction"]) != candidate["construction_sha256"]:
                raise ValueError("Current authored construction differs")
        rows.append({"case_id": current["case_id"], "construction_sha256": new_hashes})
    output = HERE / "current-runtime-reproof-canonical-equivalence.json"
    output.write_text(json.dumps({
        "format": "c110919-current-canonical-equivalence-v1",
        "historical_canonical_manifest_sha256": sha(canonical),
        "reproof_manifest_sha256": sha(harness),
        "runtime_manifest_sha256": runtime,
        "selected_cases": 20, "candidate_constructions": 80,
        "unchanged_case_order_and_constructions": True, "cases": rows
    }, indent=2) + "\n")
    print(json.dumps({"cases": 20, "candidate_constructions": 80,
                      "proof_sha256": sha(output)}))

if __name__ == "__main__":
    main()
