"""Independent original hydrant delivery audit; never accepts diagnostics."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from analysis import check_joins, original, required, rows
from hydrant import ASSIGNMENT, CASES, measure_original_history
from native_runner import CAMERAS, FRAMES


def require(ok, message):
    if not ok:
        raise ValueError(message)


def decode(path, expected):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-count_frames', '-show_entries', 'stream=nb_read_frames,width,height,r_frame_rate',
        '-of', 'json', str(path)], capture_output=True, text=True, check=True, timeout=120)
    stream = json.loads(probe.stdout)['streams'][0]
    require(stream.get('nb_read_frames') == str(FRAMES) and
            stream.get('r_frame_rate') in ('20/1', '20') and
            (stream.get('width'), stream.get('height')) == expected,
            'original full camera decode/profile missing')
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path),
                    '-f', 'null', '-'], capture_output=True, check=True, timeout=180)
    return {'decoded_frames': FRAMES, 'width': expected[0], 'height': expected[1]}


def audit_attempt(attempt, processed, case_id, decoder=decode):
    attempt, processed = Path(attempt), Path(processed)
    require(attempt.is_dir() and not attempt.is_symlink(), 'original attempt missing')
    cases = {ASSIGNMENT + '__' + case.suffix: case for case in CASES}
    require(case_id in cases, 'unknown exact hydrant case')
    site, source = original(attempt, case_id)
    history = rows(required(attempt, 'original-hydrant-history.jsonl'))
    check_joins(attempt, history)
    measurement = measure_original_history(history, site, cases[case_id])
    require(measurement['target_frame_count'] > 0, 'original target activity missing')
    decoded = {}
    for name in CAMERAS:
        size = (1920, 1080) if name == 'overview' else (1280, 720)
        decoded[name] = decoder(required(attempt, name + '.mkv'), size)
        require(decoded[name].get('decoded_frames') == FRAMES,
                'original full camera decode missing')
    require(processed.is_file() and not processed.is_symlink(),
            'saved original physical result missing')
    result = json.loads(processed.read_text(encoding='utf-8'))
    require(result.get('case_id') == case_id and
            result.get('diagnostic_fixture') is False and
            result.get('physical_acceptance_claimed') is False and
            result.get('legal_verdict_claimed') is False,
            'source-bound original nonclaim physical result required')
    return {'format': 'c150098-original-delivery-audit-v1', 'case_id': case_id,
        'activity': cases[case_id].activity, 'side': cases[case_id].side,
        'exception_kind': cases[case_id].exception,
        'map_sha256': site['map_sha256'], 'hydrant_identity_sha256': site['hydrant_identity_sha256'],
        'parallel_parking_authority_sha256': site['parallel_parking_authority_sha256'],
        'original_frame_count': FRAMES, 'target_activity_frames': measurement['target_frame_count'],
        'minimum_target_side_gap_m': measurement['minimum_longitudinal_gap_m'],
        'legal_distance_convention': 'unresolved_review', 'camera_decodes': decoded,
        'source_sha256': source,
        'processed_result_sha256': hashlib.sha256(processed.read_bytes()).hexdigest(),
        'physical_visibility': 'requires_independent_review',
        'municipal_authority': 'requires_independent_review',
        'exception_necessity': 'requires_independent_review',
        'legal_status': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--processed', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior hydrant delivery audit')
    args.output.write_text(json.dumps(audit_attempt(args.attempt, args.processed,
                                                    args.case), indent=2) + '\n',
                           encoding='utf-8')


if __name__ == '__main__':
    main()
