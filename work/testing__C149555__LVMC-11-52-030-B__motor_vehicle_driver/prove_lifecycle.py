"""CPU proof of capture, exit, owner release, and saved-only order."""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from freight_contract import VARIANTS


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    variant = args.case.removeprefix(ROOT.name + "__")
    if args.case != ROOT.name + "__" + variant or variant not in VARIANTS:
        raise ValueError("unknown exact freight case")
    output_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve(strict=True)
    if REPO / ".runtime-work" not in output_root.parents:
        raise ValueError("runtime output must remain under .runtime-work")
    sys.path.insert(0, str(REPO / "runtime"))
    from scenario_pipeline.worker_exchange.native_output import seal_capture
    from scenario_pipeline.worker_exchange.saved_processing import (
        _closure, acknowledge_owner_release, record_native_exit, run)

    with tempfile.TemporaryDirectory(dir=output_root, prefix="c149555-lifecycle-") as name:
        scratch = Path(name)
        attempt = scratch / "attempt"
        attempt.mkdir()
        (attempt / "construction.json").write_text(json.dumps({"case_id": args.case}) + "\n")
        (attempt / "config.json").write_text(json.dumps({"selected_case_id": args.case}) + "\n")
        (attempt / "runner.py").write_text("# synthetic lifecycle fixture\n")
        (attempt / "trace.jsonl").write_text('{"frame": 0}\n')
        (attempt / "video_frames.jsonl").write_text('{"frame": 0}\n')
        (attempt / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "case_id": args.case}) + "\n")
        seal = seal_capture(attempt, frames=1, restoration={"restored": True},
                            errors=[], encoder_exit_codes={"diagnostic": 0},
                            context={"scope": "synthetic lifecycle fixture"})
        exit_receipt = record_native_exit(attempt)
        try:
            _closure(attempt, None, "native", False)
        except ValueError as error:
            if "owner-release" not in str(error):
                raise
        else:
            raise AssertionError("saved processing accepted no owner release")
        owner_path = scratch / "owner-release.json"
        owner = acknowledge_owner_release(attempt, owner_path, True)
        _closure(attempt, owner_path, "native", False)
        try:
            run(ROOT / "execution-manifest.json", args.case, attempt,
                scratch / "processing", REPO / "runtime/library",
                scratch / "unused-validator", owner_receipt=owner_path)
        except (ValueError, KeyError) as error:
            rejection = str(error)
        else:
            raise AssertionError("incomplete synthetic acquisition unexpectedly processed")
        if not (scratch / "processing" / "v0001").is_dir():
            raise AssertionError("saved processing was not entered")
        events = seal["events"] + [exit_receipt["event"], owner["event"],
                                    "saved_processing_started"]
        print(json.dumps({"case_id": args.case, "events": events,
                          "synthetic_fixture": True, "saved_processing_rejection": rejection,
                          "physical_acceptance_claimed": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
