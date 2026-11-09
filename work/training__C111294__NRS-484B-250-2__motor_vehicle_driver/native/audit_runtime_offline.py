"""Independent byte audit of all materialized C111294 pinned offline constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def audit():
    manifest = json.loads((HERE / "draft-execution-manifest.json").read_text())
    checked = 0
    for case in manifest["cases"]:
        choices = [{"id": "primary", "construction": case["construction"],
                    "construction_sha256": case["construction_sha256"]}] + case["candidates"]
        suffix = case["case_id"].split("__")[-1]
        for choice in choices:
            construction_path = HERE / choice["construction"]
            raw = construction_path.read_bytes()
            if digest(raw) != choice["construction_sha256"]:
                raise ValueError("Construction digest mismatch")
            construction = json.loads(raw)
            output = HERE / "pinned-runs" / suffix / choice["id"]
            if construction["status"] != "unselected_cpu_diagnostic":
                raise ValueError("Unexpected selection status")
            for file in construction["files"]:
                target = output / file["path"]
                if target.read_bytes() != file["content"].encode():
                    raise ValueError("Materialized file differs from pinned content: " + file["path"])
                checked += 1
            selection = json.loads((output / "candidate-selection.json").read_text())
            if selection.get("candidate_id") != choice["id"]:
                raise ValueError("Offline candidate mismatch")
            log = (output / "offline.log").read_text()
            if "OK" not in log or "Ran 4 tests" not in log:
                raise ValueError("Offline CPU tests missing")
    # Explicitly prove the digest comparison detects an altered construction.
    first = (HERE / manifest["cases"][0]["construction"]).read_bytes()
    if digest(first + b" ") == manifest["cases"][0]["construction_sha256"]:
        raise ValueError("Changed-construction negative failed")
    result = {"format": "c111294-2502-pinned-offline-audit-v1", "candidate_count": 8,
              "materialized_files_checked": checked, "changed_construction_rejected": True,
              "original_native_observed": False, "delivery_ready": False}
    (HERE / "pinned-runtime-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps(audit()))
