"""Independent byte audit of C111603 frozen offline package materialization."""
import hashlib
import json

from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def audit():
    manifest = json.loads((HERE / "draft-execution-manifest.json").read_text())
    proof = json.loads((HERE / "pinned-offline-proof.json").read_text())
    if manifest["status"] != "draft_not_selected" or proof["candidate_count"] != 8:
        raise ValueError("C111603 offline package status changed")
    checked = 0
    candidates = 0
    for case in manifest["cases"]:
        suffix = case["case_id"].split("__")[-1]
        choices = [{"id": "primary", "construction": case["construction"],
                    "construction_sha256": case["construction_sha256"]}] + case["candidates"]
        for choice in choices:
            path = HERE / choice["construction"]
            raw = path.read_bytes()
            if sha(raw) != choice["construction_sha256"]:
                raise ValueError("Pinned construction digest differs")
            construction = json.loads(raw)
            if construction["status"] != "unselected_cpu_diagnostic":
                raise ValueError("Unexpected selected status")
            output = HERE / "pinned-runs" / suffix / choice["id"]
            for item in construction["files"]:
                target = output / item["path"]
                if target.read_bytes() != item["content"].encode():
                    raise ValueError("Materialized file differs: " + item["path"])
                checked += 1
            selection = json.loads((output / "candidate-selection.json").read_text())
            if selection["candidate_id"] != choice["id"]:
                raise ValueError("Pinned candidate differs")
            log = (output / "offline.log").read_text()
            if "Ran 3 tests" not in log or "OK" not in log:
                raise ValueError("Offline tests missing")
            candidates += 1
    first = (HERE / manifest["cases"][0]["construction"]).read_bytes()
    if sha(first + b" ") == manifest["cases"][0]["construction_sha256"]:
        raise ValueError("Changed construction was not detected")
    result = {"format": "c111603-3079a-pinned-offline-audit-v1",
              "candidate_count": candidates, "materialized_files_checked": checked,
              "changed_construction_rejected": True,
              "original_native_observed": False, "delivery_ready": False}
    (HERE / "pinned-offline-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps(audit(), sort_keys=True))
