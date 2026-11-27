"""Diagnostic-only positive audit wiring and missing-source rejection."""
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
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--saved-root', required=True)
    parser.add_argument('--mode', choices=('positive', 'missing_source'), required=True)
    args = parser.parse_args()
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release
    from worker_exchange.media import audit as audit_media
    root = Path(args.attempt).resolve()
    saved = Path(args.saved_root).resolve() / 'v0001'
    processing = saved / 'processing.json'
    decode = saved / 'primary-decode-with-map.json'
    frames = len((root / 'video_frames.jsonl').read_text().splitlines())
    if args.mode == 'positive':
        if not (root / 'capture-seal.json').exists():
            (root / 'converted/manifest.json').unlink(missing_ok=True)
            (root / 'acquisition-provenance.json').write_text(json.dumps({
                'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
            seal_capture(root, frames=frames,
                         restoration={'restored': True, 'settings_readback': 'CPU fixture protocol'},
                         errors=[], encoder_exit_codes={'synthetic': 0})
            record_native_exit(root)
            acknowledge_owner_release(root, root / 'owner-release.json', True)
        if not decode.exists():
            audit_media(saved / 'analysis/raw.mkv', frames,
                        mapping_sha256=sha(root / 'video_frames.jsonl'), receipt=decode)
        result = audit(root, processing, decode, args.case, protocol_fixture=True)
        if result['passed'] is not False or result['physical_acceptance_claimed'] is not False:
            raise ValueError('CPU fixture made a physical delivery claim')
        print(json.dumps(result, indent=2))
        return 0
    negative = root.parent / (root.name + '-negative-audit')
    shutil.copytree(root, negative, copy_function=os.link)
    (negative / 'safety-zone-site.json').unlink()
    try:
        audit(negative, processing, decode, args.case, protocol_fixture=True)
    except ValueError as error:
        if 'sealed original missing or changed: safety-zone-site.json' not in str(error):
            raise
        print('Expected rejection:', error)
        return 2
    raise ValueError('missing original safety-zone site was accepted')


if __name__ == '__main__':
    raise SystemExit(main())
