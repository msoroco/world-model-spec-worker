"""Exercise source-bound synthetic motion completion states for one exact case.

This does not establish original Native motion or a legal outcome.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
sys.path[:0] = [str(REPO / "runtime"), str(REPO / "runtime/scenario_pipeline")]

from scenario_pipeline.worker_exchange.native_output import physical_result


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def build(case: str, kind: str, output: Path) -> dict:
    construction = json.loads((PACKAGE / "constructions" / f"{case}-primary.json").read_text())
    config = json.loads(next(item["content"] for item in construction["files"]
                             if item["path"] == "config.json"))
    scratch = REPO / ".runtime-work/c136495-temp"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="physical-c136495-", dir=scratch) as temp:
        root = Path(temp)
        write_json(root / "config.json", config)
        write_json(root / "acquisition-provenance.json",
                   {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True})
        if kind != "missing_evidence":
            write_json(root / "classification.json", {"status": "unresolved"})
        path_m = 153.0 if kind == "complete_motion" else 5.0
        with (root / "trace.jsonl").open("w") as trace, (root / "video_frames.jsonl").open("w") as mapping:
            for index in range(600):
                frame = 1000 + index
                time_s = round(index / 20, 2)
                trace.write(json.dumps({"frame": frame, "time_s": time_s,
                                        "position_m": [path_m * index / 599, 0]}) + "\n")
                mapping.write(json.dumps({"carla_frame": frame, "time_s": time_s,
                                          "native_frame": frame, "video_frame": index}) + "\n")
        result = physical_result(root, {"target_checks": []})
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[kind]
    assert result["physical_checks"]["maneuver"]["status"] == expected
    assert result["maneuver_completed"] is (expected == "met")
    assert result["provenance_kind"] == "synthetic_fixture"
    assert result["diagnostic_fixture"] is True
    assert result["physical_acceptance_claimed"] is False
    result["case_id"] = construction["case_id"]
    write_json(output, result)
    return {"case_id": result["case_id"], "kind": kind, "status": expected,
            "source_provenance": "synthetic_fixture", "physical_acceptance_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=["probe_a", "probe_b"], required=True)
    parser.add_argument("--kind", choices=["complete_motion", "incomplete_motion", "missing_evidence"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.case, args.kind, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
