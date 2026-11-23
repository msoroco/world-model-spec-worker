"""Reproduce three saved-only diagnostic outcomes for one exact crossing case.

All sources are synthetic and kept under .runtime-work. No CARLA process or
legal evaluator runs here, and these results make no physical capture claim.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "tests"))

from saved_measurement import analyze, sha
from test_saved_measurement import SavedMeasurementTests, write_trace


def prove(case_index: int, kind: str) -> dict:
    fixture = SavedMeasurementTests()
    fixture.case_index = case_index
    fixture.setUp()
    try:
        attempt = fixture.attempt
        if kind == "complete_motion":
            path = attempt / "trace.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            for index, row in enumerate(rows[:100]):
                row["ego"]["position_m"][0] = -10. + index * .07
                row["ego"]["velocity_mps"] = [1.4, 0., 0.]
                row["controls"]["ego"] = {"throttle": .3, "brake": 0.}
            write_trace(path, rows)
            media_path = attempt / "media-receipt.json"
            media = json.loads(media_path.read_text())
            media["trace_sha256"] = sha(path)
            media_path.write_text(json.dumps(media))
        elif kind == "missing_evidence":
            (attempt / "site/packet.json").unlink()
        elif kind != "incomplete_motion":
            raise ValueError("unknown physical diagnostic outcome")
        sources = {"trace.jsonl": sha(attempt / "trace.jsonl"),
                   "video_frames.jsonl": sha(attempt / "video_frames.jsonl")}
        if kind == "missing_evidence":
            try:
                analyze(attempt)
            except ValueError as error:
                if str(error) != "Missing required source: site/packet.json":
                    raise
            else:
                raise ValueError("missing original site packet was accepted")
            sources["site/packet.json"] = "missing"
            return {"case_id": fixture.case_id, "provenance_kind": "synthetic_fixture",
                    "diagnostic_fixture": True, "maneuver_completed": False,
                    "physical_checks": {"maneuver": {"status": "unverified",
                        "method": "source-bound saved analysis rejects absent reviewed site packet",
                        "sources": sources}}, "realized_observables": {},
                    "physical_acceptance_claimed": False, "legal_judgment": "unresolved"}
        report, result = analyze(attempt)
        expected = kind == "complete_motion"
        if result["maneuver_completed"] is not expected:
            raise ValueError("diagnostic motion outcome differs from expected")
        sources["site/packet.json"] = sha(attempt / "site/packet.json")
        return {"case_id": fixture.case_id, "provenance_kind": "synthetic_fixture",
                "diagnostic_fixture": True,
                "maneuver_completed": result["maneuver_completed"],
                "physical_checks": {"maneuver": {
                    "status": "met" if expected else "not_met",
                    "method": "source-bound 900-frame approach, stop, queue and motion continuity measurement",
                    "sources": sources}},
                "realized_observables": result["crossing_observables"],
                "analysis_format": report["format"],
                "physical_acceptance_claimed": False, "legal_judgment": "unresolved"}
    finally:
        fixture.doCleanups()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-index", type=int, choices=range(6), required=True)
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion",
                                          "missing_evidence"), required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    if args.result.exists():
        raise ValueError("retain previous physical proof result")
    result = prove(args.case_index, args.kind)
    args.result.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"case_id": result["case_id"], "kind": args.kind,
                      "status": result["physical_checks"]["maneuver"]["status"],
                      "diagnostic_fixture": True}))


if __name__ == "__main__":
    main()
