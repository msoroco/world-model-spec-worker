"""Independent original flashing-red delivery audit; diagnostics are rejected."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from analysis import check_joins, original, required, rows
from flashing_red_native import ASSIGNMENT, CASES, measure_original
from native_runner import CAMERAS, FRAMES


def require(ok, message):
    if not ok:
        raise ValueError(message)


def decode(path, expected):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-count_frames', '-show_entries', 'stream=nb_read_frames,width,height,r_frame_rate',
        '-of', 'json', str(path)], capture_output=True, text=True, check=True, timeout=120)
    stream = json.loads(probe.stdout)['streams'][0]
    require(stream.get('nb_read_frames') == str(FRAMES)
            and stream.get('r_frame_rate') in ('20/1', '20')
            and (stream.get('width'), stream.get('height')) == expected,
            'original full camera decode/profile missing')
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path),
                    '-f', 'null', '-'], capture_output=True, check=True, timeout=180)
    return {'decoded_frames': FRAMES, 'width': expected[0], 'height': expected[1]}


def audit_attempt(attempt, processed, case_id, decoder=decode):
    attempt, processed = Path(attempt), Path(processed)
    require(attempt.is_dir() and not attempt.is_symlink(), 'original attempt missing')
    cases = {ASSIGNMENT + '__' + case.suffix: case for case in CASES}
    require(case_id in cases, 'unknown exact flashing-red case')
    site, source = original(attempt, case_id)
    history = rows(required(attempt, 'original-flashing-red-history.jsonl'))
    check_joins(attempt, history)
    measurement = measure_original(history, site, cases[case_id])
    require(measurement['stop_observations'], 'original complete cessation missing')
    decoded = {}
    for name in CAMERAS:
        size = (1920, 1080) if name == 'overview' else (1280, 720)
        decoded[name] = decoder(required(attempt, name + '.mkv'), size)
        require(decoded[name].get('decoded_frames') == FRAMES,
                'original full camera decode missing')
    require(processed.is_file() and not processed.is_symlink(),
            'saved original physical result missing')
    result = json.loads(processed.read_text(encoding='utf-8'))
    require(result.get('case_id') == case_id
            and result.get('diagnostic_fixture') is False
            and result.get('physical_acceptance_claimed') is False
            and result.get('legal_verdict_claimed') is False,
            'source-bound original nonclaim physical result required')
    return {'format': 'c24751-original-delivery-audit-v1', 'case_id': case_id,
        'reference_kind': cases[case_id].reference,
        'map_sha256': site['map_sha256'],
        'signal_identity_sha256': site['signal_identity_sha256'],
        'occluder_identity_sha256': site['occluder_identity_sha256'],
        'stop_geometry_sha256': site['stop_geometry_sha256'],
        'original_frame_count': FRAMES,
        'flashing_red_transitions': measurement['flashing_red_transitions'],
        'surveyed_reference_m': measurement['surveyed_reference_m'],
        'stop_observations': measurement['stop_observations'],
        'post_stop_right_to_proceed': 'unresolved_applicable_rules',
        'camera_decodes': decoded, 'source_sha256': source,
        'processed_result_sha256': hashlib.sha256(processed.read_bytes()).hexdigest(),
        'physical_visibility': 'requires_independent_review',
        'legal_status': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--processed', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior flashing-red delivery audit')
    args.output.write_text(json.dumps(audit_attempt(args.attempt, args.processed,
                                                    args.case), indent=2) + '\n',
                           encoding='utf-8')


if __name__ == '__main__':
    main()
