"""CPU protocol test; never produces a physical acceptance receipt."""

import argparse
import json
import os
import shutil
from pathlib import Path

from delivery_audit import audit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--saved-root", required=True)
    parser.add_argument("--mode", choices=("positive", "missing_source"), required=True)
    args = parser.parse_args(argv)
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release

    root = Path(args.saved_root).resolve()
    attempt = root / "attempt"
    version = root / "derived/v0001"
    processing = version / "processing.json"
    decode = version / "primary-decode-with-map.json"
    if args.mode == "positive":
        frames = sum(1 for _ in (attempt / "video_frames.jsonl").open())
        if not (attempt / "capture-seal.json").exists():
            (attempt / "acquisition-provenance.json").write_text(json.dumps({
                "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
            seal_capture(attempt, frames=frames, restoration={"restored": True,
                "settings_readback": "CPU fixture protocol"}, errors=[],
                encoder_exit_codes={"synthetic": 0})
            record_native_exit(attempt)
            acknowledge_owner_release(attempt, attempt / "owner-release.json", True)
        from worker_exchange.media import audit as audit_media
        from delivery_audit import sha
        if not decode.exists():
            audit_media(version / "analysis/raw.mkv", frames,
                        mapping_sha256=sha(attempt / "video_frames.jsonl"), receipt=decode)
        result = audit(attempt, processing, decode, args.case, protocol_fixture=True)
        if result["passed"] is not False or result["physical_acceptance_claimed"] is not False:
            raise ValueError("CPU fixture made a physical delivery claim")
        print(json.dumps(result, indent=2))
        return 0
    negative = root / "negative-audit"
    shutil.copytree(attempt, negative, copy_function=os.link)
    (negative / "parking-context.json").unlink()
    try:
        audit(negative, processing, decode, args.case, protocol_fixture=True)
    except ValueError as error:
        if "sealed original missing or changed: parking-context.json" not in str(error):
            raise
        print("Expected rejection:", error)
        return 2
    raise ValueError("missing original context was accepted")


if __name__ == "__main__":
    raise SystemExit(main())
