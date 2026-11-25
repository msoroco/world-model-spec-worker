"""Exercise the source-bound delivery policy on diagnostic saved attempts.

This proves CPU plumbing and tamper rejection. Only delivery_audit.py on a
reviewed 900-frame Native attempt can establish physical delivery.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

import delivery_audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--negative-camera", action="store_true")
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--processing", type=Path)
    args = parser.parse_args()
    if args.production:
        if args.processing is None:
            raise ValueError("production delivery needs saved processing receipt")
        print(json.dumps(delivery_audit.audit_delivery(args.attempt,
                                                        args.processing, args.case)))
        return
    if args.negative_camera:
        scratch = Path(".runtime-work/c125697-2502-audit-probe").resolve()
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            copied = Path(temporary) / "attempt"
            shutil.copytree(args.attempt, copied)
            with (copied / "overview.mkv").open("ab") as handle:
                handle.write(b"tampered camera")
            delivery_audit.audit_sources(copied, args.case, 9, diagnostic=True)
        raise AssertionError("tampered camera was accepted")
    receipt = delivery_audit.audit_sources(args.attempt, args.case, 9,
                                            diagnostic=True)
    try:
        delivery_audit.audit_delivery(args.attempt, args.attempt / "none.json",
                                      args.case)
    except ValueError as error:
        if "diagnostic fixture cannot establish Native delivery" not in str(error):
            raise
    else:
        raise AssertionError("diagnostic fixture was accepted as delivery")
    print(json.dumps({"case_id": args.case, "source_bound": True,
                      "native_delivery_claimed": False,
                      "source_manifest_sha256": receipt["manifest_sha256"]}))


if __name__ == "__main__":
    main()
