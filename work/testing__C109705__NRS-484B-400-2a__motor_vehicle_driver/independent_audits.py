"""Independent, source-bound CPU checks for C109705 approach packages.

These checks establish diagnostic consistency, not Native physical or legal
acceptance. They deliberately reread original files instead of trusting the
finalizer's measured-values object.
"""
import hashlib
import json
import argparse
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from shapely.geometry import LineString, Polygon


REQUIRED = (
    'config.json', 'road_context.json', 'approach_history.jsonl',
    'video_frames.jsonl', 'result.json', 'overview.mkv', 'approach.mkv',
    'reference_corner.mkv', 'driver_reference.mkv',
)
FIXED = (
    'native_map_id', 'intersection_id', 'approach_road_id',
    'approach_lane_id', 'outgoing_road_id', 'connector_road_id',
    'both_highways_two_directional', 'intended_turn', 'centerline_kind',
    'centerline_xy_m', 'right_half_polygon_xy_m',
)


def _read(path):
    return json.loads(path.read_text())


def _rows(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError(f'Missing rows: {path.name}')
    return rows


def audit_delivery(attempt):
    attempt = Path(attempt)
    missing = [name for name in REQUIRED if not (attempt / name).is_file()]
    if missing:
        raise ValueError('Missing original evidence: ' + ', '.join(missing))
    result = _read(attempt / 'result.json')
    config = _read(attempt / 'config.json')
    context = _read(attempt / 'road_context.json')
    if result.get('case_id') != config.get('selected_case_id'):
        raise ValueError('Case identity differs from original config')
    hashes = result.get('source_evidence_hashes', {})
    for name in REQUIRED:
        if name == 'result.json':
            continue
        actual = hashlib.sha256((attempt / name).read_bytes()).hexdigest()
        if hashes.get(name) != actual:
            raise ValueError('Missing or stale original source hash: ' + name)
    if context.get('both_highways_two_directional') is not True or context.get('intended_turn') != 'left':
        raise ValueError('Two-way left-turn activation absent')
    if context.get('centerline_kind') not in ('marked', 'imaginary'):
        raise ValueError('Centerline authority absent')
    center = LineString(context['centerline_xy_m'])
    right = Polygon(context['right_half_polygon_xy_m'])
    if center.length <= 0 or not right.is_valid or right.area <= 0:
        raise ValueError('Invalid road geometry')
    frames = _rows(attempt / 'video_frames.jsonl')
    frame_ids = {r['native_frame'] for r in frames}
    if len(frame_ids) != len(frames):
        raise ValueError('Duplicate original frame')
    approach = _rows(attempt / 'approach_history.jsonl')
    entry = context.get('first_entry_frame')
    before = [r for r in approach if r['frame'] < entry and not r['body_in_intersection']]
    if not before or any(r['frame'] not in frame_ids for r in before):
        raise ValueError('No synchronized pre-entry body samples')
    distances = []
    for row in before:
        body = Polygon(row['ego_body_vertices_xy_m'])
        if not body.is_valid or body.area <= 0 or not right.covers(body):
            raise ValueError('Complete body leaves sourced right half')
        distances.append(center.distance(body.centroid))
    measured = result.get('measured_values', {})
    stated = measured.get('body_centroid_centerline_distance_m')
    if not isinstance(stated, list) or len(stated) != len(distances) or any(abs(a-b) > 1e-6 for a,b in zip(stated,distances)):
        raise ValueError('Reported offset differs from original bodies')
    if measured.get('approach_body_fully_in_right_half') is not True:
        raise ValueError('Right-half result missing')
    return {'case_id': result['case_id'], 'centerline_kind': context['centerline_kind'],
            'fixed': {key: context.get(key) for key in FIXED},
            'cameras': config['cameras'], 'rate_hz': config['rate_hz'],
            'duration_s': config['duration_s'], 'offsets_m': distances,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def audit_comparison(near_attempt, far_attempt, expected_kind):
    near = audit_delivery(near_attempt)
    far = audit_delivery(far_attempt)
    if near['centerline_kind'] != expected_kind or far['centerline_kind'] != expected_kind:
        raise ValueError('Wrong comparison centerline kind')
    for key in ('fixed', 'cameras', 'rate_hz', 'duration_s'):
        if near[key] != far[key]:
            raise ValueError('Fixed comparison condition differs: ' + key)
    if len(near['offsets_m']) != len(far['offsets_m']) or not all(a < b for a,b in zip(near['offsets_m'],far['offsets_m'])):
        raise ValueError('Declared near/far body offset not observed')
    return {'comparison_kind': expected_kind, 'near_case_id': near['case_id'],
            'far_case_id': far['case_id'], 'near_offsets_m': near['offsets_m'],
            'far_offsets_m': far['offsets_m'],
            'nearest_centerline_judgment': 'unresolved; no statutory numeric cutoff',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    if args.negative:
        with TemporaryDirectory(dir='.runtime-work') as temp:
            target = Path(temp)
            for name in REQUIRED:
                if name != 'approach_history.jsonl':
                    os.link(args.attempt / name, target / name)
            audit_delivery(target)
        raise AssertionError('Missing required original source passed')
    result = audit_delivery(args.attempt)
    if result['case_id'] != args.case:
        raise ValueError('Delivery audit selected another case')
    from sys import path
    path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime/scenario_pipeline'))
    from worker_exchange.media import audit, check_four_view_sources
    from worker_exchange.native_output import physical_result
    names = ('overview', 'approach', 'reference_corner', 'driver_reference')
    sources = {name: args.attempt / (name + '.mkv') for name in names}
    check_four_view_sources(sources)
    count = len(_rows(args.attempt / 'video_frames.jsonl'))
    map_sha = hashlib.sha256((args.attempt / 'video_frames.jsonl').read_bytes()).hexdigest()
    decoded = {name: audit(video, count, mapping_sha256=map_sha)['rgb_sequence_sha256']
               for name, video in sources.items()}
    if not (args.attempt / 'capture/native/frames.jsonl').is_file() or not (args.attempt / 'trace.jsonl').is_file():
        raise ValueError('Missing original Native frame or trace source')
    physical = physical_result(args.attempt, {'case_id': args.case, 'target_checks': []})
    if physical['physical_checks']['maneuver']['status'] != 'met':
        raise ValueError('Physical completion source classifier did not observe full turn')
    print(json.dumps({'case_id': args.case, 'passed': True, 'source_bound': True,
                      'full_video_decode': decoded, 'physical_motion_status': 'met',
                      'pixel_scope': 'full RGB pixel stream hashed; actor visibility unverified',
                      'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    cli()
