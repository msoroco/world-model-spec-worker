"""Independently bind curve offline receipts to materialized source bytes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parents[1]
ROOT = CASE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    manifest_path = HERE / "draft-execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    receipt = json.loads((HERE / "pinned-runtime-proof.json").read_text())
    if receipt["manifest_sha256"] != sha(manifest_path) or len(receipt["entries"]) != 4:
        raise ValueError("Pinned curve manifest/receipt mismatch")
    case = manifest["cases"][0]
    expected = {item["id"]: item for item in
                [{"id": "primary", "construction": case["construction"],
                  "construction_sha256": case["construction_sha256"]}, *case["candidates"]]}
    files = 0
    for row in receipt["entries"]:
        item = expected.pop(row["candidate_id"])
        construction_path = HERE / item["construction"]
        if (row["case_id"] != CASE.name + "__probe_03" or
                sha(construction_path) != item["construction_sha256"] or
                row["construction_sha256"] != item["construction_sha256"]):
            raise ValueError("Changed curve construction digest")
        construction = json.loads(construction_path.read_text())
        output = ROOT / row["materialized_dir"]
        selection = json.loads((output / "candidate-selection.json").read_text())
        if (selection["construction_sha256"] != item["construction_sha256"] or
                row["log_sha256"] != sha(output / "offline.log") or
                row["tests"] != 4 or row["exit_code"] != 0 or
                row["simulation_started"] is not False):
            raise ValueError("Pinned curve selection or log mismatch")
        for file in construction["files"]:
            target = output / file["path"]
            if not target.is_file() or target.read_text() != file["content"]:
                raise ValueError("Materialized curve source differs: " + file["path"])
            files += 1
    if expected:
        raise ValueError("Missing pinned curve candidate")
    changed = json.loads((HERE / case["construction"]).read_text())
    changed["recording_description"] += " altered"
    digest = hashlib.sha256((json.dumps(changed, indent=2, allow_nan=False) + "\n").encode()).hexdigest()
    if digest == case["construction_sha256"]:
        raise ValueError("Changed curve construction negative failed")
    result = {"format": "c104496-curve-independent-pinned-audit-v1",
              "candidates": len(receipt["entries"]), "materialized_files": files,
              "changed_construction_rejected": True,
              "original_native_observed": False, "delivery_ready": False}
    (HERE / "pinned-runtime-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    result = audit()
    print(json.dumps({"candidates": result["candidates"],
                      "materialized_files": result["materialized_files"]}))
