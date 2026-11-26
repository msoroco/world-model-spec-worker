"""Saved-source delivery audit for one exact pedestrian case.

The CPU fixture proves decoding and packet joins. Original Native acceptance
still requires a reviewed source and the independent production audit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import decode_video
from native_recorder import SIZES
from saved_entry import CAMERAS, PACKETS, build_report


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(case_id, attempt, plan):
    attempt = Path(attempt).resolve()
    planned = json.loads(Path(plan).read_text())
    if case_id not in {item['case_id'] for item in planned['cases']}:
        raise ValueError('delivery case outside exact pedestrian plan')
    report = build_report(attempt)
    if report['case_id'] != case_id:
        raise ValueError('delivery case differs from saved source')
    frames = report['sample_count']
    if frames < 3 or set(report['source_sha256']) != {
            'scene.json', *PACKETS, *(name + '.mkv' for name in CAMERAS)}:
        raise ValueError('required original sources or frames missing')
    videos = {name: decode_video(attempt / (name + '.mkv'), frames=frames,
                                 size=SIZES[name]) for name in CAMERAS}
    if any(videos[name]['source_sha256'] != report['source_sha256'][name + '.mkv']
           for name in CAMERAS):
        raise ValueError('decoded source differs from measured source')
    return {'format': 'c227824-saved-delivery-acceptance-v1',
            'case_id': case_id, 'provenance_kind': report['provenance_kind'],
            'diagnostic_fixture': report['diagnostic_fixture'],
            'source_sha256': report['source_sha256'],
            'synchronized_frames': frames, 'videos': videos,
            'entry_measurement': report['measurement'],
            'all_participants_joined': True, 'time_join_verified': True,
            'four_view_full_decode': True, 'actual_pixels_decoded': True,
            'actual_pixels_verified': False,
            'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    receipt = audit(args.case, args.attempt, args.plan)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'case_id': args.case, 'diagnostic_fixture':
                      receipt['diagnostic_fixture'], 'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
