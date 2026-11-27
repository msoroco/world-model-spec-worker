"""CPU protocol proof of independent stop delivery and missing-source rejection."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from delivery_audit import audit, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", choices=("positive", "missing_source"), required=True)
    args = parser.parse_args()
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release

    root = Path(args.output).resolve()
    fixture = Path(args.fixture).resolve()
    if args.mode == "positive":
        root.mkdir(parents=True, exist_ok=False)
        for name in ("stop-history.jsonl", "stop-scene.json", "trace.jsonl",
                     "video_frames.jsonl", "road.xodr", "config.json", "construction.json",
                     "runner.py"):
            shutil.copy2(fixture / name, root / name)
        (root / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
        analysis = root / "saved-analysis"
        analysis.mkdir()
        (analysis / "raw.mkv").write_bytes(b"synthetic protocol marker; media decode tested separately")
        shutil.copy2(fixture / "result.json", analysis / "result.json")
        decode = root / "decode.json"
        decode.write_text(json.dumps({"format": "CPU protocol only"}) + "\n")
        processing = root / "processing.json"
        processing.write_text(json.dumps({
            "format": "worker-saved-processing", "passed": True,
            "recorded_only": True, "case_id": args.case,
            "analysis_directory": str(analysis), "result": str(analysis / "result.json"),
            "result_sha256": sha(analysis / "result.json")}) + "\n")
        frames = len((root / "video_frames.jsonl").read_text().splitlines())
        seal_capture(root, frames=frames,
                     restoration={"restored": True, "settings_readback": "CPU protocol fixture"},
                     errors=[], encoder_exit_codes={"synthetic": 0})
        record_native_exit(root)
        acknowledge_owner_release(root, root / "owner-release.json", True)
        result = audit(root, processing, decode, args.case, protocol_fixture=True,
                       media_verify=lambda *a, **kw: True)
        if result["passed"] is not False or result["physical_acceptance_claimed"] is not False:
            raise ValueError("CPU fixture made physical acceptance claim")
        print(json.dumps(result, indent=2))
        return 0
    negative = root.parent / (root.name + "-missing-source")
    shutil.copytree(root, negative)
    (negative / "stop-scene.json").unlink()
    try:
        audit(negative, negative / "processing.json", negative / "decode.json", args.case,
              protocol_fixture=True, media_verify=lambda *a, **kw: True)
    except ValueError as error:
        if "sealed original stop source missing or changed: stop-scene.json" not in str(error):
            raise
        print("Expected rejection:", error)
        return 2
    raise ValueError("missing original stop scene was accepted")


if __name__ == "__main__":
    raise SystemExit(main())
