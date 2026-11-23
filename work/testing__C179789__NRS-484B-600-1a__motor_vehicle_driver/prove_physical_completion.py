"""Exercise complete, incomplete and missing sealed motion sources on CPU."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from physical_completion import classify, digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion",
                                           "missing_evidence"), required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    trace = args.output / "trace.jsonl"
    seal = args.output / "trace-seal.json"
    stride = .4 if args.kind == "complete_motion" else 0.
    trace.write_text("".join(json.dumps({"frame": i,
                                          "position_m": [round(i * stride, 6), 0., 0.]}) + "\n"
                             for i in range(900)), encoding="utf-8")
    seal.write_text(json.dumps({"case_id": args.case, "trace_sha256": digest(trace)},
                               sort_keys=True) + "\n", encoding="utf-8")
    if args.kind == "missing_evidence":
        seal.unlink()
    result = classify(trace, seal, args.case)
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[args.kind]
    if result["physical_checks"]["maneuver"]["status"] != expected:
        raise ValueError("measured motion outcome differs")
    if result["maneuver_completed"] != (expected == "met"):
        raise ValueError("completion boolean differs")
    if args.kind == "complete_motion":
        original_seal = seal.read_text(encoding="utf-8")
        seal.write_text(json.dumps({"case_id": args.case,
                                    "trace_sha256": "0" * 64}) + "\n", encoding="utf-8")
        if classify(trace, seal, args.case)["physical_checks"]["maneuver"]["status"] != "unverified":
            raise ValueError("changed source seal was accepted")
        seal.write_text(original_seal, encoding="utf-8")
    result["case_id"] = args.case
    (args.output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True)
                                                + "\n", encoding="utf-8")
    print(args.case, args.kind, expected, "source-bound synthetic diagnostic")


if __name__ == "__main__":
    main()
