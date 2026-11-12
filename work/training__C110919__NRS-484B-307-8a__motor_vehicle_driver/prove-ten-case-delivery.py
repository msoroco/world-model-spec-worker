"""Exercise ten primary source audits without accepting synthetic recordings."""
import hashlib
import json
from pathlib import Path

from ten_case_delivery_audit import audit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "update038-ten-case-probe-manifest.json"
INDEX = HERE / "update038-ten-case-matrix-index.json"
RUNS = ROOT / ".runtime-work/c110919-update038-ten-case-matrix"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def reject(call):
    try:
        call()
    except ValueError as error:
        return str(error)
    raise ValueError("Damaged or synthetic delivery was accepted")


def main():
    manifest = json.loads(MANIFEST.read_text())
    index = json.loads(INDEX.read_text())
    require(index["manifest_sha256"] == sha(MANIFEST) and
            len(manifest["cases"]) == 10 and index["candidates"] == 40,
            "Ten-case final-hash probe missing")
    outcomes = []
    negatives = {}
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        run = RUNS / suffix / "primary"
        attempt = run / "compatibility"
        processing = run / "saved/v0001/processing.json"
        row = next((item for item in index["results"] if
                    item["case_id"] == entry["case_id"] and
                    item["candidate_id"] == "primary"), None)
        require(row is not None and sha(HERE / row["proof"]) == row["sha256"],
                "Primary matrix receipt differs")
        outcome = audit(entry["case_id"], entry["construction_sha256"],
                        attempt, processing, diagnostic=True)
        require(outcome["source_shape_passed"] is True and
                outcome["passed"] is False and
                outcome["physical_or_legal_acceptance_claimed"] is False and
                set(outcome["source_frame_counts"].values()) == {480},
                "Diagnostic source was accepted or incomplete")
        outcomes.append({"case_id": entry["case_id"],
                         "construction_sha256": entry["construction_sha256"],
                         "saved_processing_sha256": sha(processing),
                         "source_sha256": outcome["source_sha256"],
                         "source_shape_passed": True,
                         "original_delivery_accepted": False})
        negatives[suffix + "__wrong_construction"] = reject(lambda: audit(
            entry["case_id"], "0" * 64, attempt, processing, diagnostic=True))
        negatives[suffix + "__synthetic_as_original"] = reject(lambda: audit(
            entry["case_id"], entry["construction_sha256"], attempt, processing,
            diagnostic=False))
    proof = {"format": "c110919-ten-case-delivery-cpu-audit-v1",
             "manifest_sha256": sha(MANIFEST), "matrix_index_sha256": sha(INDEX),
             "auditor_sha256": sha(HERE / "ten_case_delivery_audit.py"),
             "cases_checked": len(outcomes), "outcomes": outcomes,
             "negative_rejections": negatives, "canonical_selected": False,
             "original_native_accepted": False}
    target = HERE / "update038-ten-case-delivery-audit-proof.json"
    target.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"cases_checked": len(outcomes),
                      "negative_rejections": len(negatives),
                      "proof_sha256": sha(target), "original_native_accepted": False}))


if __name__ == "__main__":
    main()
