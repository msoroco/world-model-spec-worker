"""Decode every saved primary frame and audit the sealed original projection."""

import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import audit
from pixel_checks import check as pixel_presence


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--processing", type=Path, required=True)
    parser.add_argument("--decode-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    attempt = args.attempt.resolve()
    processing = args.processing.resolve()
    saved = json.loads(processing.read_text(encoding="utf-8"))
    video = Path(saved["analysis_directory"]) / "raw.mkv"
    mapping = attempt / "video_frames.jsonl"
    count = len(mapping.read_text(encoding="utf-8").splitlines())
    if count != 900:
        raise ValueError("original Native 900-frame source required")
    from worker_exchange.media import audit as decode
    args.decode_receipt.parent.mkdir(parents=True, exist_ok=True)
    decode(video, count, checkers={"pixel_presence": (sha(Path(__file__).with_name("pixel_checks.py")),
                                                   pixel_presence)},
           mapping_sha256=sha(mapping), receipt=args.decode_receipt)
    result = audit(attempt, processing, args.decode_receipt, args.case)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
