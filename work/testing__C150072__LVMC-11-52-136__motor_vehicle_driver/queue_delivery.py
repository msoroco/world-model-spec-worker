"""Retain an independent audit of one original access-aisle delivery."""
import argparse
import json
from pathlib import Path

from delivery_audit import audit
from worker_exchange.media import audit as audit_media


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processed-root', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior original audit report')
    versions = sorted(args.processed_root.glob('v*/processing.json'))
    if not versions:
        raise ValueError('saved processing receipt missing')
    processing = versions[-1]
    stage = processing.parent / 'analysis'
    mapping = args.attempt / 'video_frames.jsonl'
    import hashlib
    frame_count = len(mapping.read_text(encoding='utf-8').splitlines())
    decode_receipt = processing.parent / 'access-aisle-source-decode.json'
    audit_media(stage / 'raw.mkv', frame_count,
                mapping_sha256=hashlib.sha256(mapping.read_bytes()).hexdigest(),
                receipt=decode_receipt)
    report = audit(args.attempt, processing, decode_receipt, args.case)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
