"""Diagnostic software proof of Native closure and saved-processing order."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def probe(attempt: Path) -> list[str]:
    if "SCENARIO_PIPELINE_OUTPUT_ROOT" not in os.environ:
        raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before import")
    repo = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo / "runtime/scenario_pipeline"))
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, _closure

    scratch = repo / ".runtime-work/c130864-physical-tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lifecycle-", dir=scratch) as temporary:
        root = Path(temporary)
        for name in ("construction.json", "runner.py", "trace.jsonl",
                     "video_frames.jsonl"):
            shutil.copyfile(attempt / name, root / name)
        (root / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True
        }) + "\n")
        frames = len((root / "video_frames.jsonl").read_text().splitlines())
        seal = seal_capture(root, frames=frames, restoration={"restored": True},
                            errors=[], context={"diagnostic_lifecycle": True})
        if seal["events"] != EVENTS[:3] or seal["diagnostic_fixture"] is not True:
            raise ValueError("diagnostic closure sequence differs")
        exit_record = record_native_exit(root)
        if exit_record["event"] != "native_exit":
            raise ValueError("native exit receipt not joined")
        try:
            _closure(root, None, "native", False)
        except ValueError as error:
            if "owner-release receipt" not in str(error):
                raise
        else:
            raise ValueError("Native saved processing accepted absent owner release")
        owner = root / "owner-release.json"
        acknowledge_owner_release(root, owner, acknowledged=True)
        _closure(root, owner, "native", True)
        # A synthetic fixture has no simulator owner. This event records only
        # that the saved-processing precondition accepted the diagnostic chain.
        return EVENTS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    args = parser.parse_args()
    print("\n".join(probe(args.attempt)))


if __name__ == "__main__":
    main()
