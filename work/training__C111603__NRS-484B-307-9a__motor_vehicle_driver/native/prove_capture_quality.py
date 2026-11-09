"""CPU source-shape proof for capture-bound fallback decisions."""
import json
from pathlib import Path
import tempfile

from build import CASE, HERE, write
from fallback_quality import from_capture
from prove_original_processing import fixture


def prove():
    positive = negative = 0
    records = []
    for suffix in ("witness_1", "witness_2"):
        bundle = HERE / "drafts" / suffix / "primary"
        with tempfile.TemporaryDirectory(prefix="c111603-quality-") as temp:
            directory = Path(temp)
            review_path = fixture(bundle, directory)
            review = json.loads(review_path.read_text())
            review["quality_signal_other_visible_frames"] = list(range(480))
            review_path.write_text(json.dumps(review, indent=2) + "\n")
            result = from_capture(bundle, directory, review_path, synthetic_fixture=True)
            assert result["triggers"] == {"fallback1": True, "fallback2": False,
                                           "fallback3": False}
            assert not result["original_native_observed"] and not result["delivery_ready"]
            positive += 1
            records.append({"case_id": suffix, "metrics": result["metrics"]})
            for frames in ([], [0, 0], [480], None):
                changed = dict(review)
                changed["quality_signal_other_visible_frames"] = frames
                review_path.write_text(json.dumps(changed, indent=2) + "\n")
                try:
                    from_capture(bundle, directory, review_path, synthetic_fixture=True)
                except ValueError:
                    negative += 1
                else:
                    raise AssertionError("Invalid visibility review passed")
            review_path.write_text(json.dumps(review, indent=2) + "\n")
            try:
                from_capture(bundle, directory, review_path)
            except ValueError:
                negative += 1
            else:
                raise AssertionError("Marker capture accepted as original")
    proof = {"format": "c111603-3079a-capture-quality-shape-proof-v1",
             "assignment_id": CASE.name, "positive_count": positive,
             "negative_count": negative, "records": records,
             "synthetic_fixture_only": True, "original_native_observed": False,
             "delivery_ready": False}
    write(HERE / "capture-quality-shape-proof.json", proof)
    return proof


if __name__ == "__main__":
    print(json.dumps(prove(), sort_keys=True))
