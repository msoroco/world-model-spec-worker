"""Bind exact staged construction, compatibility and saved CPU receipts."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
FOLDER = HERE.parents[1]
REPO = FOLDER.parent.parent
STAGE = HERE / "clearance_guard"
LABELS = ("primary", "fallback1", "fallback2", "fallback3")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    manifest_path = FOLDER / "clearance-guard-draft-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if len(manifest["cases"]) != 1 or manifest.get("canonical_selection") is not False:
        raise ValueError("Only one unselected staged case is allowed")
    entry = manifest["cases"][0]
    policy = (FOLDER / "hazard_sweep_policy.py").read_text()
    proofs = []
    for label in LABELS:
        row = entry if label == "primary" else next(x for x in entry["candidates"] if x["id"] == label)
        construction = FOLDER / row["construction"]
        bundle = json.loads(construction.read_text())
        if sha(construction) != row["construction_sha256"]:
            raise ValueError("Staged construction hash changed: " + label)
        embedded = [x["content"] for x in bundle["files"] if x["path"] == "hazard_sweep_policy.py"]
        if embedded != [policy]:
            raise ValueError("Staged policy differs from guarded source: " + label)
        output = REPO / ".runtime-work" / ("c109749-clearance-guard-" + label)
        compat = output.with_name(output.name + "-compat")
        saved = output.with_name(output.name + "-saved") / "v0001/processing.json"
        receipt = json.loads((compat / "compatibility.json").read_text())
        processing = json.loads(saved.read_text())
        if (receipt.get("case_id") != entry["case_id"] or
                receipt.get("candidate_id") != label or
                receipt.get("construction_sha256") != row["construction_sha256"] or
                receipt.get("passed") is not True):
            raise ValueError("Exact compatibility binding failed: " + label)
        if processing.get("case_id") != entry["case_id"]:
            raise ValueError("Saved processing case differs: " + label)
        for suffix in ("offline", "compatibility", "saved"):
            log = STAGE / (label + "-" + suffix + ".log")
            if not log.is_file() or not log.read_text().strip():
                raise ValueError("Staged CPU log missing: " + label + " " + suffix)
        proofs.append({"candidate_id": label,
                       "construction_sha256": row["construction_sha256"],
                       "compatibility_receipt_sha256": sha(compat / "compatibility.json"),
                       "negative_log_sha256": sha(compat / "negative-analysis.log"),
                       "saved_processing_sha256": sha(saved),
                       "offline_log_sha256": sha(STAGE / (label + "-offline.log")),
                       "compatibility_log_sha256": sha(STAGE / (label + "-compatibility.log")),
                       "saved_log_sha256": sha(STAGE / (label + "-saved.log"))})
    result = {"format": "worker-staged-clearance-guard-proof",
              "case_id": entry["case_id"],
              "manifest_sha256": sha(manifest_path),
              "policy_sha256": sha(FOLDER / "hazard_sweep_policy.py"),
              "proofs": proofs,
              "staged_exact_cpu_paths_passed": True,
              "canonical_selection": False,
              "native_feasibility_proven": False,
              "legal_result_asserted": False}
    (STAGE / "proof-index.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps({"candidate_count": len(run()["proofs"]),
                      "staged_exact_cpu_paths_passed": True}))
