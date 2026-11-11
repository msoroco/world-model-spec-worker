"""Audit exact selected synthetic saved pairs and bind them to CPU proofs.

This checks diagnostic provenance and the declared crossing-location difference.
It does not establish physical or statutory acceptance.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "native"))
from audit_saved_pair import CASES, audit, load, require, sha  # noqa: E402

CANDIDATES = ("primary", "fallback1", "fallback2", "fallback3")


def selected_side(case, candidate):
    folder = ROOT / "update015-selected-proof" / case / candidate
    proof = load(folder / "proof.json")
    require(proof["case_id"] == ROOT.name + "__" + case and
            proof["candidate_id"] == candidate, "Selected proof identity differs")
    require(proof["processing_receipt"] == str((folder / "processing.json").relative_to(ROOT))
            and sha(folder / "processing.json") == proof["processing_sha256"],
            "Selected processing proof binding differs")
    require(sha(ROOT / proof["manifest"]) == proof["manifest_sha256"],
            "Selected manifest proof binding differs")
    receipt = load(folder / "processing.json")
    require(receipt["native_revision"]["construction_sha256"] ==
            proof["construction_sha256"], "Selected construction binding differs")
    construction = load(Path(receipt["analysis_directory"]) / "construction.json")
    require(construction.get("case_id") == proof["case_id"] and
            construction.get("status") == "selected_delivery_preparation_original_unverified",
            "Selected construction identity or status differs")
    return folder / "processing.json", proof


def run():
    rows = []
    for branch, (reference, contrast) in CASES.items():
        for candidate in CANDIDATES:
            left, left_proof = selected_side(reference, candidate)
            right, right_proof = selected_side(contrast, candidate)
            result = audit(left, right, branch, candidate)
            require(result["receipt_sha256"] == [left_proof["processing_sha256"],
                                                   right_proof["processing_sha256"]],
                    "Pair receipt binding differs")
            result["format"] = "c111662-selected-synthetic-pair-audit-v1"
            result["scope"] = "selected synthetic saved diagnostic; no original, physical, or legal acceptance"
            result["proof_sha256"] = [sha(ROOT / "update015-selected-proof" / case /
                                          candidate / "proof.json") for case in (reference, contrast)]
            rows.append(result)
    return {"format": "c111662-selected-synthetic-pair-matrix-v1",
            "assignment_id": ROOT.name, "pair_count": len(rows), "passed": len(rows) == 8,
            "pairs": rows,
            "scope": "CPU selected synthetic diagnostic only; independent original delivery audit remains"}


if __name__ == "__main__":
    output = ROOT / "update015-selected-pair-audit.json"
    data = run()
    output.write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps({"passed": data["passed"], "pair_count": data["pair_count"],
                      "sha256": sha(output)}))
