"""CPU-only pedestrian path comparison; not original Native motion."""

import hashlib
import json
from pathlib import Path

from path import compare_requested_paths, target


if __name__ == "__main__":
    positive = compare_requested_paths()
    negative = []
    for case, frame in (("unknown", 0), ("crosswalk", -1), ("outside", 600)):
        try:
            target(case, frame)
        except ValueError as error:
            negative.append({"case": case, "frame": frame, "rejected": str(error)})
        else:
            raise AssertionError("Invalid path request accepted")
    proof = {"format": "worker-cpu-pedestrian-path-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": positive, "negative": negative}
    path = Path(__file__).with_name("path-proof.json")
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"passed": True, "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
