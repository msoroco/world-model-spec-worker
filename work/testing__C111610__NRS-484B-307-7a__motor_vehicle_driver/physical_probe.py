"""Run pinned physical assessment on explicit synthetic outcome variants."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
KINDS = {"complete_motion", "incomplete_motion", "missing_evidence"}


def probe(suffix, kind, output):
    if kind not in KINDS:
        raise ValueError("unknown physical outcome")
    work_root = (REPO / ".runtime-work").resolve()
    output_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    if output_root != work_root and work_root not in output_root.parents:
        raise ValueError("export runtime output root under .runtime-work first")
    scratch = work_root / "c111610-nov24-owner/tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    construction = json.loads((ROOT / ("construction-" + suffix + ".json")).read_text())
    config = next(json.loads(item["content"]) for item in construction["files"]
                  if item["path"] == "config.json")
    fixture = json.loads((ROOT / ("diagnostic-" + suffix + ".json")).read_text())
    files = fixture["files"]
    with tempfile.TemporaryDirectory(dir=scratch, prefix="physical-") as temporary:
        attempt = Path(temporary)
        (attempt / "config.json").write_text(json.dumps(config) + "\n")
        for name in ("trace.jsonl", "video_frames.jsonl", "acquisition-provenance.json"):
            (attempt / name).write_text(files[name])
        if kind != "missing_evidence":
            rows = [json.loads(line) for line in files["body_history.jsonl"].splitlines()]
            if kind == "incomplete_motion":
                first = rows[0]
                for row in rows:
                    row["body_vertices_m"] = first["body_vertices_m"]
                    row["heading_deg"] = first["heading_deg"]
            (attempt / "body_history.jsonl").write_text(
                "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))
        from worker_exchange.native_output import physical_result
        result = physical_result(attempt, {"case_id": construction["case_id"],
                                           "target_checks": []})
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        observed = result["physical_checks"]["maneuver"]["status"]
        if observed != expected:
            raise ValueError(f"expected {expected} physical status, got {observed}")
        result["fixture_kind"] = kind
        output = Path(output)
        if output.exists() or output.parent.resolve() != ROOT:
            raise ValueError("choose fresh output under exact assignment")
        output.write_text(json.dumps(result, indent=2) + "\n")
        return observed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", choices=sorted(KINDS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(args.case, args.kind, probe(args.case, args.kind, args.output))


if __name__ == "__main__":
    main()
