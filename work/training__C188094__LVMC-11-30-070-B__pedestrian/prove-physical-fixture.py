"""CPU-only crossing completion fixtures and saved-processing lifecycle proof."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path):
    return [json.loads(row) for row in path.read_text().splitlines() if row]


def assess(attempt, kind):
    source = attempt / 'actor-poses.jsonl'
    context = attempt / 'crossing-context.json'
    if kind == 'missing_evidence':
        rows = []
    else:
        rows = lines(source)
        if kind == 'incomplete_motion':
            rows = rows[:100]
    bounds = json.loads(context.read_text())['roadway_bounds_m']
    before = any(row['pedestrian_y_m'] < bounds['min_y'] for row in rows)
    after = any(row['pedestrian_y_m'] > bounds['max_y'] for row in rows)
    joined = len(rows) == 600 and all(row['video_frame'] == i for i, row in enumerate(rows))
    if not rows:
        status = 'unverified'
    elif before and after and joined:
        status = 'met'
    else:
        status = 'not_met'
    sources = [{'path': 'crossing-context.json', 'sha256': sha(context)}]
    if kind != 'missing_evidence':
        sources.append({'path': 'actor-poses.jsonl', 'sha256': sha(source),
                        'synthetic_slice_rows': len(rows)})
    return {'format': 'c188094-physical-cpu-fixture', 'fixture_kind': kind,
            'physical_checks': {'maneuver': {'status': status,
                'method': 'synthetic original-pose before/after roadway bounds with 600-frame join',
                'sources': sources}}, 'maneuver_completed': status == 'met',
            'realized_observables': {'synthetic_crossed_roadway': {'value': True,
                'unit': 'boolean', 'method': 'diagnostic original pose join'}} if status == 'met' else {},
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'original_native_observed': False, 'business_district_confirmed': False,
            'legal_verdict_claimed': False}


def lifecycle(attempt, saved):
    processing = json.loads((saved / 'processing.json').read_text())
    if (processing.get('passed') is not True or processing.get('recorded_only') is not True
            or processing.get('originals_preserved') is not True
            or processing.get('timestamp_joins', {}).get('frames') != 600):
        raise ValueError('Saved processing lacks original 600-frame handoff')
    for name in ('actor-poses.jsonl', 'video_frames.jsonl', 'crossing-context.json'):
        if not (attempt / name).is_file():
            raise ValueError('Missing original synthetic source: ' + name)
    return {'events': ['capture_finished', 'encoders_closed', 'restoration_verified',
                       'native_exit', 'owner_released', 'saved_processing_started'],
            'exit_code': 0, 'synthetic_lifecycle_fixture': True,
            'saved_processing_sha256': sha(saved / 'processing.json')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--saved', required=True, type=Path)
    parser.add_argument('--kind', required=True,
                        choices=['complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'])
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.kind == 'lifecycle':
        result = lifecycle(args.attempt, args.saved)
    else:
        result = assess(args.attempt, args.kind)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[args.kind]
        if result['physical_checks']['maneuver']['status'] != expected:
            raise ValueError('Unexpected CPU fixture result: ' + expected)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
