"""Exercise selected original-capture processors on synthetic source-shape fixtures.

Fixtures test rejection and measurement logic only. They are never original Native
recordings and cannot establish physical, visual, or legal acceptance.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / "native"))
from prove_original_processing import prove as prove_intersection  # noqa: E402
from prove_original_divided import prove as prove_divided  # noqa: E402

CASES = ("reference", "contrast", "divided_reference", "divided_opening")
CANDIDATES = ("primary", "fallback1", "fallback2", "fallback3")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    entries = []
    for case in CASES:
        for candidate in CANDIDATES:
            bundle = REPO / ".runtime-work/update015-c111662-selected/final" / case / candidate / "offline"
            construction = ROOT / "native/package-selected" / case / candidate / "construction.json"
            if not bundle.is_dir() or sha(bundle / "construction.json") != sha(construction):
                raise ValueError("Selected original processor bundle missing or stale: " + case + "/" + candidate)
            result = (prove_divided if case.startswith("divided_") else prove_intersection)(bundle)
            if (result["case_id"] != ROOT.name + "__" + case or
                    result["candidate_id"] != candidate or
                    result["positive_count"] != 1 or result["negative_count"] != 7 or
                    result["original_native_observed"] is not False or
                    result["delivery_ready"] is not False):
                raise ValueError("Selected original processor source-shape proof failed")
            entries.append({"case_id": result["case_id"], "candidate_id": candidate,
                            "construction_sha256": sha(construction), **result})
    return {"format": "c111662-selected-original-processor-shape-matrix-v1",
            "assignment_id": ROOT.name, "candidate_count": len(entries),
            "positive_count": sum(x["positive_count"] for x in entries),
            "negative_count": sum(x["negative_count"] for x in entries),
            "entries": entries, "passed": len(entries) == 16,
            "scope": "selected CPU synthetic source-shape fixture; no original or acceptance"}


if __name__ == "__main__":
    result = run()
    output = ROOT / "update015-selected-original-processor-shape-matrix.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "candidate_count": result["candidate_count"],
                      "positive_count": result["positive_count"],
                      "negative_count": result["negative_count"], "sha256": sha(output)}))
