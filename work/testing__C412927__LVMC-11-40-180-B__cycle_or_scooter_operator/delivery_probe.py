"""Mock protocol proof and missing-original-source rejection for delivery audit."""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from delivery_audit import audit, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--saved-root', type=Path, required=True)
    parser.add_argument('--mode', choices=('positive', 'missing_source'), required=True)
    args = parser.parse_args()
    root = args.saved_root.resolve() / 'attempt'
    saved = args.saved_root.resolve() / 'processed/v0001'
    processing = saved / 'processing.json'
    decode = saved / 'primary-decode-with-map.json'
    if args.mode == 'positive':
        from worker_exchange.media import audit as audit_media
        frames = len((root / 'video_frames.jsonl').read_text().splitlines())
        if not decode.exists():
            audit_media(saved / 'analysis/raw.mkv', frames,
                        mapping_sha256=sha(root / 'video_frames.jsonl'), receipt=decode)
        result = audit(root, processing, decode, args.case, protocol_fixture=True)
        if result['passed'] is not False or result['physical_acceptance_claimed'] is not False:
            raise ValueError('CPU fixture made a physical delivery claim')
        print(json.dumps(result, indent=2))
        return 0
    negative = args.saved_root.resolve() / 'negative-audit'
    if negative.exists():
        shutil.rmtree(negative)
    shutil.copytree(root, negative, copy_function=os.link)
    (negative / 'signed-road-site.json').unlink()
    try:
        audit(negative, processing, decode, args.case, protocol_fixture=True)
    except ValueError as error:
        if 'sealed original missing or changed: signed-road-site.json' not in str(error):
            raise
        print('Expected rejection:', error)
        return 2
    raise ValueError('missing original signed roadway site was accepted')


if __name__ == '__main__':
    raise SystemExit(main())
