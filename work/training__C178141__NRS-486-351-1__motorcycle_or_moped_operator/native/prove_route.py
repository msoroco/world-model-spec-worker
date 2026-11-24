"""CPU-only route comparison proof, not a Native capture."""

import hashlib
import json
from pathlib import Path

from route import compare_requested_routes, target


if __name__ == "__main__":
    positive = compare_requested_routes()
    negative = []
    for case, frame in (("unknown", 0), ("beside", -1), ("between", 600)):
        try:
            target(case, frame)
        except ValueError as error:
            negative.append({"case": case, "frame": frame, "rejected": str(error)})
        else:
            raise AssertionError("Invalid route request accepted")
    proof = {"format": "worker-cpu-motorcycle-route-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": positive, "negative": negative}
    path = Path(__file__).with_name("route-proof.json")
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"passed": True, "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
