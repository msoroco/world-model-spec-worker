"""Save and challenge the controlled 480-frame intersection traversal proposal."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "native"))
from traversal import check_pair, measure, synthetic_samples


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejected(rows, path, digest) -> bool:
    try:
        measure(rows, path, digest)
    except ValueError:
        return True
    return False


def main():
    geometric = check_pair()
    outputs = {}
    for case in ("traversal_reference", "traversal_contrast"):
        path = HERE / "traversal-cpu" / case / "saved-synthetic-frames.json"
        rows = synthetic_samples(case)
        write(path, rows)
        digest = sha(path)
        measured = measure(rows, path, digest)
        tampered = json.loads(path.read_text())
        tampered[333]["body_xy_m"][0][1] += .5
        missing_frame = rows[:333] + rows[334:]
        no_survey = json.loads(path.read_text())
        no_survey[333]["two_way_native_survey"] = False
        no_speed = json.loads(path.read_text())
        no_speed[333]["speed_m_s"] = float("nan")
        negatives = {
            "changed_body_rejected": rejected(tampered, path, digest),
            "missing_frame_rejected": rejected(missing_frame, path, digest),
            "missing_survey_rejected": rejected(no_survey, path, digest),
            "nonfinite_speed_rejected": rejected(no_speed, path, digest),
            "wrong_hash_rejected": rejected(rows, path, "0" * 64),
        }
        if not all(negatives.values()):
            raise ValueError("Traversal negative failed")
        outputs[case] = {"saved_source": str(path.relative_to(HERE)),
                         "saved_sha256": digest, "measure": measured,
                         "negative_proofs": negatives}
    if outputs["traversal_reference"]["measure"]["moving_left_traversal_frames"] != 0:
        raise ValueError("Reference relation differs")
    if outputs["traversal_contrast"]["measure"]["moving_left_traversal_frames"] < 10:
        raise ValueError("Contrast relation differs")
    receipt = {"format": "c110454-traversal-synthetic-cpu-proof-v1",
               "status": "cpu_proposal_not_native_capture", "geometry": geometric,
               "cases": outputs, "original_native_verified": False,
               "strict_delivery_ready": False}
    write(HERE / "traversal-cpu" / "proof.json", receipt)
    print(json.dumps({"status": receipt["status"], "case_frames": 480,
                      "left_traversal_frames": [outputs[k]["measure"]["moving_left_traversal_frames"]
                                                 for k in outputs]}))


if __name__ == "__main__":
    main()
