"""CPU contract proof for original-attempt review sequencing."""
import hashlib
import json
from pathlib import Path
import tempfile

from prepare_original_attempt import prepare
from prove_source_bridge import SCRATCH, fixture


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reject(label, attempt, review, expected, diagnostic=False):
    try:
        prepare(attempt, review, diagnostic=diagnostic)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(label + ": wrong rejection: " + str(error)) from error
        return label
    raise AssertionError(label + ": unreviewed attempt accepted")


def main():
    SCRATCH.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c111071-original-prep-", dir=SCRATCH) as temp:
        root = Path(temp)
        attempt, review, _ = fixture(root / "diagnostic")
        positive = prepare(attempt, review, diagnostic=True)
        if (positive["frames"] != 600 or
                positive["physical_detector_causation_verified"] or
                not positive["diagnostic_only"]):
            raise AssertionError("Diagnostic bridge made a physical claim")
        missing_attempt, missing_review, _ = fixture(root / "missing_capture")
        negatives = [reject("missing_capture", missing_attempt, missing_review,
                            "Original Native capture manifest absent")]
        other_attempt, other_review, _ = fixture(root / "other_source")
        capture = other_attempt / "capture"
        capture.mkdir()
        (capture / "manifest.json").write_text(
            json.dumps({"source_kind": "synthetic_fixture"}) + "\n")
        negatives.append(reject("non_original", other_attempt, other_review,
                                "Original Native capture required"))
        stale_attempt, stale_review, review_value = fixture(root / "stale_review")
        review_value["source_sha256"]["native_raw_readback.jsonl"] = "0" * 64
        stale_review.write_text(json.dumps(review_value) + "\n")
        negatives.append(reject("stale_review", stale_attempt, stale_review,
                                "Review does not bind", diagnostic=True))
    receipt = {"format": "c111071-original-attempt-preparation-cpu-v1",
               "passed": True, "diagnostic_only": True,
               "original_native_observed": False,
               "script_sha256": sha(HERE / "prepare_original_attempt.py"),
               "positive_frames": 600, "negative_rejections": negatives}
    path = HERE / "original-attempt-preparation-proof.json"
    path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"passed": True, "negative_rejections": negatives,
                      "proof_sha256": sha(path)}, sort_keys=True))


if __name__ == "__main__":
    main()
