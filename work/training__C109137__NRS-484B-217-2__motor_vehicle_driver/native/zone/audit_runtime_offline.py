"""Independently bind pinned offline receipts to exact materialized files."""
import hashlib
import json
from pathlib import Path

from build import HERE


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    manifest_path = HERE / "draft-execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    receipt = json.loads((HERE / "pinned-runtime-proof.json").read_text())
    if receipt["manifest_sha256"] != sha(manifest_path) or len(receipt["entries"]) != 8:
        raise ValueError("Pinned manifest/receipt mismatch")
    expected = {}
    for case in manifest["cases"]:
        for item in [{"id": "primary", "construction": case["construction"],
                      "construction_sha256": case["construction_sha256"]},
                     *case["candidates"]]:
            expected[(case["case_id"], item["id"])] = item
    files = 0
    for row in receipt["entries"]:
        key = row["case_id"], row["candidate_id"]
        item = expected.pop(key)
        construction_path = HERE / item["construction"]
        if sha(construction_path) != item["construction_sha256"] or \
                row["construction_sha256"] != item["construction_sha256"]:
            raise ValueError("Changed construction digest")
        construction = json.loads(construction_path.read_text())
        destination = HERE.parents[3] / row["materialized_dir"]
        selection = json.loads((destination / "candidate-selection.json").read_text())
        if selection["construction_sha256"] != item["construction_sha256"] or \
                row["log_sha256"] != sha(destination / "offline.log") or \
                row["tests"] != 3 or row["exit_code"] != 0 or \
                row["simulation_started"] is not False:
            raise ValueError("Pinned selection or log mismatch")
        for file in construction["files"]:
            target = destination / file["path"]
            if not target.is_file() or target.read_text() != file["content"]:
                raise ValueError("Materialized source differs: " + file["path"])
            files += 1
    if expected:
        raise ValueError("Missing pinned candidates")
    # A fully edited construction cannot retain its manifest digest.
    first = manifest["cases"][0]
    source = json.loads((HERE / first["construction"]).read_text())
    source["recording_description"] += " altered"
    changed = hashlib.sha256((json.dumps(source, indent=2, allow_nan=False) + "\n").encode()).hexdigest()
    if changed == first["construction_sha256"]:
        raise ValueError("Changed-construction negative failed")
    result = {"format": "c109137-zone-independent-pinned-audit-v1",
              "candidates": len(receipt["entries"]), "materialized_files": files,
              "changed_construction_rejected": True,
              "original_native_observed": False, "delivery_ready": False}
    (HERE / "pinned-runtime-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    result = audit()
    print(json.dumps({"candidates": result["candidates"],
                      "materialized_files": result["materialized_files"]}))
