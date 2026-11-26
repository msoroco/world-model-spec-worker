"""Independent original truck-following delivery audit; diagnostics rejected."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from analysis import check_joins, check_source, required, rows
from truck_following import CASES, audit_original_frames, audit_case_realization
from native_packet import AID, VIEWS


def require(ok, message):
    if not ok:
        raise ValueError(message)


def decode(path, expected):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-count_frames', '-show_entries', 'stream=nb_read_frames,width,height,r_frame_rate',
        '-of', 'json', str(path)], capture_output=True, text=True, check=True, timeout=120)
    stream = json.loads(probe.stdout)['streams'][0]
    require(stream.get('nb_read_frames') == '900'
            and stream.get('r_frame_rate') in ('20/1', '20')
            and (stream.get('width'), stream.get('height')) == expected,
            'original full camera decode/profile missing')
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path),
                    '-f', 'null', '-'], capture_output=True, check=True, timeout=180)
    return {'decoded_frames': 900, 'width': expected[0], 'height': expected[1]}


def audit_attempt(attempt, processed, case_id, decoder=decode):
    attempt, processed = Path(attempt), Path(processed)
    require(attempt.is_dir() and not attempt.is_symlink(), 'original attempt missing')
    cases = {AID + '__' + case.suffix: case for case in CASES}
    require(case_id in cases, 'unknown exact truck case')
    diagnostic, source = check_source(attempt, case_id)
    require(not diagnostic and source.get('capture-seal.json'),
            'source-bound original truck seal required')
    context_path = required(attempt, 'truck_context.json')
    seal = json.loads(required(attempt, 'capture-seal.json').read_text(encoding='utf-8'))
    require(seal.get('sources', {}).get('truck_context.json') == hashlib.sha256(context_path.read_bytes()).hexdigest(),
            'original truck context is not byte sealed')
    context = json.loads(context_path.read_text(encoding='utf-8'))
    for key in ('road_source_sha256', 'route_geometry_sha256', 'weather_sha256',
                'condition_context', 'participant_blueprint_sha256'):
        require(context.get(key), 'reviewed original truck context missing: ' + key)
    history = rows(required(attempt, 'original-truck-history.jsonl'))
    check_joins(attempt, history)
    measurement = audit_original_frames({'source_kind': 'sealed_native_original_frames',
        'case_id': case_id, 'frames': history}, case_id=case_id)
    measurement['original_source_sha256'] = source['original-truck-history.jsonl']
    realization = audit_case_realization(cases[case_id], measurement, case_id=case_id)
    decoded = {}
    for name in VIEWS:
        size = (1920, 1080) if name == 'overview' else (1280, 720)
        decoded[name] = decoder(required(attempt, name + '.mkv'), size)
        require(decoded[name].get('decoded_frames') == 900,
                'original full camera decode missing')
    require(processed.is_file() and not processed.is_symlink(),
            'saved original physical result missing')
    result = json.loads(processed.read_text(encoding='utf-8'))
    require(result.get('case_id') == case_id
            and result.get('diagnostic_fixture') is False
            and result.get('physical_acceptance_claimed') is False
            and result.get('legal_verdict_claimed') is False,
            'source-bound original nonclaim physical result required')
    return {'format': 'c149237-original-delivery-audit-v1', 'case_id': case_id,
        'original_frame_count': 900, 'measurement': measurement,
        'original_context': context,
        'construction_realization': realization,
        'camera_decodes': decoded, 'source_sha256': source,
        'processed_result_sha256': hashlib.sha256(processed.read_bytes()).hexdigest(),
        'physical_visibility': 'requires_independent_review',
        'conditions_permit': 'unresolved', 'entry_without_danger': 'unresolved',
        'legal_status': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--processed', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior truck delivery audit')
    args.output.write_text(json.dumps(audit_attempt(args.attempt, args.processed,
                                                    args.case), indent=2) + '\n',
                           encoding='utf-8')


if __name__ == '__main__':
    main()
