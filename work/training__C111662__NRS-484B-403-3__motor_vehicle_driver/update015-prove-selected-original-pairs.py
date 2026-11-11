"""CPU-test selected original pair auditor with synthetic source-shape fixtures."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / "native"))
from audit_original_pair import PAIRS, audit  # noqa: E402
from prove_original_processing import fixture as fixture_intersection  # noqa: E402
from prove_original_divided import fixture as fixture_divided  # noqa: E402

CANDIDATES = ("primary", "fallback1", "fallback2", "fallback3")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reject(name, call):
    try:
        call()
    except (ValueError, FileNotFoundError):
        return name
    raise ValueError("Original pair audit accepted negative: " + name)


def run():
    rows = []
    with tempfile.TemporaryDirectory() as temporary:
        temp = Path(temporary)
        for branch, (reference, contrast) in PAIRS.items():
            fixture = fixture_divided if branch == "divided_opening" else fixture_intersection
            for candidate in CANDIDATES:
                bundles = [REPO / ".runtime-work/update015-c111662-selected/final" /
                           case / candidate / "offline" for case in (reference, contrast)]
                for bundle in bundles:
                    if not bundle.is_dir():
                        raise ValueError("Selected offline bundle missing: " + str(bundle))
                attempts = [temp / branch / candidate / case for case in (reference, contrast)]
                for path in attempts:
                    path.mkdir(parents=True)
                reviews = [fixture(bundle, path) for bundle, path in zip(bundles, attempts)]
                args = (*[bundles[0], attempts[0], reviews[0], bundles[1], attempts[1], reviews[1]], branch)
                result = audit(*args, synthetic_fixture=True)
                if (result["candidate_id"] != candidate or not result["passed"] or
                        result["source_kind"] != "synthetic_fixture" or
                        result["accepted"] is not False or result["legal_verdict"] is not None):
                    raise ValueError("Synthetic selected original pair result changed")
                negatives = [reject("missing_review", lambda: audit(
                    bundles[0], attempts[0], reviews[0], bundles[1], attempts[1],
                    attempts[1] / "absent-review.json", branch, synthetic_fixture=True)),
                    reject("same_attempt", lambda: audit(
                    bundles[0], attempts[0], reviews[0], bundles[1], attempts[0],
                    reviews[0], branch, synthetic_fixture=True))]
                if candidate == "primary":
                    other = REPO / ".runtime-work/update015-c111662-selected/final" / contrast / "fallback1/offline"
                    other_attempt = temp / branch / "cross_candidate"
                    other_attempt.mkdir(parents=True)
                    other_review = fixture(other, other_attempt)
                    negatives.append(reject("changed_fixed_candidate", lambda: audit(
                        bundles[0], attempts[0], reviews[0], other, other_attempt,
                        other_review, branch, synthetic_fixture=True)))
                rows.append({"branch": branch, "candidate_id": candidate,
                             "case_ids": result["case_ids"],
                             "observed_crossing_delta_m": result["observed_crossing_delta_m"],
                             "negative_rejections": negatives,
                             "construction_sha256": [sha(bundle / "construction.json") for bundle in bundles]})
    return {"format": "c111662-selected-original-pair-fixture-proof-v1",
            "assignment_id": ROOT.name, "pair_count": len(rows),
            "negative_count": sum(len(row["negative_rejections"]) for row in rows),
            "passed": len(rows) == 8, "pairs": rows,
            "scope": "synthetic source-shape test only; no original pair, physical or legal acceptance"}


if __name__ == "__main__":
    result = run()
    path = ROOT / "update015-selected-original-pair-fixture-proof.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "pair_count": result["pair_count"],
                      "negative_count": result["negative_count"], "sha256": sha(path)}))
