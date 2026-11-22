"""Exercise selected diagnostic delivery and three source mutations per chain."""
import hashlib
import json
from pathlib import Path

from delivery_acceptance import check
from prove_delivery_negatives_update073 import prove

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    positives = []
    negatives = []
    for suffix in ("reference", "contrast"):
        case = HERE.name + "__" + suffix
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            attempt = ROOT / ".runtime-work/c177225-current-matrix" / suffix / candidate / "compat"
            result = check(attempt, case, diagnostic=True)
            if not (result["diagnostic_passed"] is True and result["delivery_accepted"] is False):
                raise ValueError("Diagnostic claimed original delivery")
            positives.append({"case_id": case, "candidate_id": candidate,
                              "result": result,
                              "source_sha256": {name: sha(attempt / name) for name in
                                                ("bus_native_rows.jsonl", "officer_signal_rows.jsonl",
                                                 "video_frames.jsonl", "four-view-receipt.json")}})
            for kind in ("missing", "tampered", "native"):
                rejected = prove(attempt, case, kind)
                if rejected["rejected"] is not True:
                    raise ValueError("Changed delivery source accepted")
                negatives.append({"case_id": case, "candidate_id": candidate,
                                  "kind": kind, "error": rejected["error"]})
            print(suffix, candidate, "delivery boundary passed", flush=True)
    if len(positives) != 8 or len(negatives) != 24:
        raise ValueError("Incomplete delivery boundary matrix")
    path = HERE / "current-runtime-delivery-audit.json"
    path.write_text(json.dumps({"format": "c177225-current-delivery-cpu-audit-v1",
                                "passed": True, "positive_diagnostics": positives,
                                "negative_rejections": negatives,
                                "original_native_accepted": False}, indent=2) + "\n")
    print(json.dumps({"positive_diagnostics": len(positives),
                      "negative_rejections": len(negatives), "sha256": sha(path)}))


if __name__ == "__main__":
    main()
