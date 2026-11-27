"""Independent full-source audit for an original 127(3) group capture.

Diagnostic fixtures cannot pass this audit. Numeric targets are engineering
checks; legal sufficiency and danger remain independent review questions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from analysis import check_frame_joins, check_source, required, rows
from motorcade_spacing import CASES, measure_original_frames
from runner import AID

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode(path, size):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-count_frames', '-show_entries', 'stream=nb_read_frames,width,height,r_frame_rate',
        '-of', 'json', str(path)], capture_output=True, text=True, check=True, timeout=120)
    stream = json.loads(probe.stdout)['streams'][0]
    require(stream.get('nb_read_frames') == '600' and
            stream.get('r_frame_rate') in ('20/1', '20') and
            (stream.get('width'), stream.get('height')) == size,
            'original four-camera full-decode profile missing')
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path),
                    '-f', 'null', '-'], capture_output=True, check=True, timeout=180)
    return {'decoded_frames': 600, 'width': size[0], 'height': size[1]}


def audit_attempt(attempt, processed, case_id, decoder=decode):
    attempt, processed = Path(attempt), Path(processed)
    require(attempt.is_dir() and not attempt.is_symlink(), 'original attempt directory missing')
    cases = {AID + '__' + item.suffix: item for item in CASES}
    require(case_id in cases, 'unknown exact group case')
    diagnostic, source = check_source(attempt, case_id)
    require(not diagnostic and source.get('capture-seal.json'),
            'source-bound original Native group seal required')
    seal = json.loads(required(attempt, 'capture-seal.json').read_text())
    context_path = required(attempt, 'caravan-context.json')
    require(seal['sources'].get('caravan-context.json') == sha(context_path),
            'original group context is not byte sealed')
    context = json.loads(context_path.read_text())
    require(context.get('case_suffix') == cases[case_id].suffix and
            context.get('group_kind') == cases[case_id].group_kind and
            context.get('group_towing') == cases[case_id].towing and
            context.get('entrant_kind') == ('combination' if cases[case_id].combination_entrant else 'vehicle'),
            'original group context differs from exact case')
    for key in ('native_road_id', 'public_highway_source',
                'outside_business_district_source', 'coordination_source',
                'weather_sha256', 'vehicle_blueprints_sha256'):
        require(context.get(key), 'reviewed original group context missing: ' + key)
    history = rows(required(attempt, 'original-group-history.jsonl'))
    check_frame_joins(attempt, history)
    measured = measure_original_frames(history, cases[case_id])
    require(all(row.get('vehicle_inventory') and row.get('velocities') is not None
                and row.get('couplings') is not None for row in history),
            'original all-participant motion or coupling history missing')
    decoded = {}
    for view in VIEWS:
        size = (1920, 1080) if view == 'overview' else (1280, 720)
        decoded[view] = decoder(required(attempt, view + '.mkv'), size)
        require(decoded[view].get('decoded_frames') == 600,
                'full original camera decode missing')
    require(processed.is_file() and not processed.is_symlink(),
            'saved-only original physical result missing')
    result = json.loads(processed.read_text())
    require(result.get('case_id') == case_id and
            result.get('diagnostic_fixture') is False and
            result.get('physical_acceptance_claimed') is False and
            result.get('legal_verdict_claimed') is False,
            'source-bound original nonclaim physical result required')
    require(abs(result.get('measured_values', {}).get('steady_front_mean_m', -1e9)
                - measured['steady_front_mean_m']) < 1e-5 and
            abs(result.get('measured_values', {}).get('steady_rear_mean_m', -1e9)
                - measured['steady_rear_mean_m']) < 1e-5,
            'saved measured gaps disagree with independent original body audit')
    lanes = [row['bodies']['entrant'].get('native_lane_id') for row in history]
    return {'format':'c160013-original-delivery-audit-v1', 'case_id':case_id,
        'original_frame_count':600,
        'measurement':{'steady_front_mean_m':measured['steady_front_mean_m'],
            'steady_rear_mean_m':measured['steady_rear_mean_m'],
            'requested_gap_m':measured['requested_gap_m'],
            'entrant_occupied_group_lane':any(lane == context['directed_driving_lane_id'] for lane in lanes),
            'entrant_lane_history_sha256':source['original-group-history.jsonl'],
            'legal_judgment':'unresolved'},
        'original_context':context,'camera_decodes':decoded,'source_sha256':source,
        'processed_result_sha256':sha(processed),
        'physical_visibility':'requires_independent_review',
        'sufficient_space':'unresolved','without_danger':'unresolved',
        'legal_status':'unresolved'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processed', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior original group audit')
    args.output.write_text(json.dumps(audit_attempt(args.attempt, args.processed,
                                                    args.case), indent=2) + '\n')
