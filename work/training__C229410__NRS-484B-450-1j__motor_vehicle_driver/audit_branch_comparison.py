"""Independent source comparison for activity and exception branch drafts.

This checks source isolation. It never supplies an authority or legal verdict.
"""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def original_direction_record(folder, context, difference, rows):
    manifest_path = folder / 'authority/manifest.json'
    if sha(manifest_path) != context.get('authority_manifest_sha256'):
        raise ValueError('Original authority manifest hash differs')
    manifest = json.loads(manifest_path.read_text())
    sources = manifest.get('sources', {})
    for name in ('station_identity', 'driveway_entrance', 'highway_boundary',
                 'activity_and_directions'):
        record = sources.get(name, {})
        path = folder / 'authority' / (name + '.source')
        expected = record.get('sha256')
        if not path.is_file() or not expected or sha(path) != expected:
            raise ValueError('Original authority source missing or changed: ' + name)
        if context.get('authority_source_sha256', {}).get(name) != expected:
            raise ValueError('Original context authority binding differs: ' + name)
    record = json.loads((folder / 'authority/activity_and_directions.source').read_text()).get(difference)
    if not isinstance(record, dict):
        raise ValueError('Original direction source record missing')
    for name in ('source_id', 'issued_by', 'directed_action'):
        if not isinstance(record.get(name), str) or not record[name].strip():
            raise ValueError('Original direction record field missing: ' + name)
    window = record.get('valid_time')
    if not isinstance(window, dict) or set(window) != {'start_s', 'end_s'}:
        raise ValueError('Original direction valid time missing')
    start, end = window['start_s'], window['end_s']
    if any(type(value) not in (int, float) for value in (start, end)) or start > end:
        raise ValueError('Original direction valid time invalid')
    if start > rows[-100]['time_s'] or end < rows[-1]['time_s']:
        raise ValueError('Original direction does not cover stationary interval')
    if difference in ('police_officer', 'official_device'):
        actor = record.get('actor_id')
        if type(actor) is not int or actor == rows[0]['actor_id']:
            raise ValueError('Original direction actor missing or equals ego')
        if not all(actor in row.get('direction_source_actor_ids', []) for row in rows[-100:]):
            raise ValueError('Original direction actor not joined to stationary frames')
    if difference == 'law' and not isinstance(record.get('citation'), str):
        raise ValueError('Original applicable-law citation missing')
    return {'source_id': record['source_id'],
            'authority_sha256': sha(folder / 'authority/activity_and_directions.source')}


def compare(base, variant, difference):
    base, variant = Path(base), Path(variant)
    if difference not in ('activity', 'traffic_conflict', 'law', 'police_officer', 'official_device'):
        raise ValueError('Unknown branch difference')
    for name in ('road.xodr', 'video_frames.jsonl', 'acquisition-provenance.json'):
        if sha(base / name) != sha(variant / name):
            raise ValueError('Fixed source differs: ' + name)
    b = json.loads((base / 'entrance-context.json').read_text())
    v = json.loads((variant / 'entrance-context.json').read_text())
    if b.get('source_kind') != v.get('source_kind'):
        raise ValueError('Source kind differs')
    for key in ('cell_id', 'entrance', 'fire_station_identity_reviewed',
                'driveway_entrance_reviewed', 'highway_side_reviewed'):
        if b.get(key) != v.get(key):
            raise ValueError('Fixed context differs: ' + key)
    if b.get('initial_activity') != 'stopped' or b.get('exception_context') != 'none':
        raise ValueError('Baseline must be unexcepted stopping')
    if difference == 'activity':
        if v.get('initial_activity') != 'standing' or v.get('exception_context') != 'none':
            raise ValueError('Standing contrast absent')
    elif v.get('initial_activity') != 'stopped' or v.get('exception_context') != difference:
        raise ValueError('Exception contrast absent')
    base_rows = load_rows(base / 'native-vehicle.jsonl')
    variant_rows = load_rows(variant / 'native-vehicle.jsonl')
    if len(base_rows) != 600 or len(variant_rows) != 600:
        raise ValueError('Six hundred source frames required')
    fixed = ('native_frame', 'video_frame', 'time_s', 'actor_id', 'blueprint_id',
             'center_xy_m', 'body_xy_m', 'speed_mps')
    for index, (left, right) in enumerate(zip(base_rows, variant_rows)):
        if any(left.get(key) != right.get(key) for key in fixed):
            raise ValueError('Ego motion or timing differs at frame ' + str(index))
        if left.get('traffic_conflict_vehicle') is not None:
            raise ValueError('Baseline traffic actor is present')
    if any(row.get('speed_mps', 999) > .1 for row in base_rows[-100:]):
        raise ValueError('Sustained source rest missing')
    if difference == 'traffic_conflict':
        for row in variant_rows:
            other = row.get('traffic_conflict_vehicle')
            if not isinstance(other, dict) or other.get('actor_id') == row.get('actor_id') or len(other.get('body_xy_m', [])) < 4:
                raise ValueError('Independent traffic actor source missing')
    elif any(row.get('traffic_conflict_vehicle') is not None for row in variant_rows):
        raise ValueError('Unselected traffic actor changed')
    if difference == 'law' and v.get('applicable_law_source_reviewed') is not True:
        raise ValueError('Applicable law source review missing')
    if difference == 'police_officer' and v.get('police_direction_source_observed') is not True:
        raise ValueError('Police direction source missing')
    if difference == 'official_device' and v.get('official_device_source_observed') is not True:
        raise ValueError('Official-device source missing')
    if b.get('source_kind') == 'original_native':
        for name in ('authority/manifest.json', 'overview.mkv', 'approach.mkv',
                     'reference_corner.mkv', 'driver_reference.mkv'):
            if not (base / name).is_file() or not (variant / name).is_file():
                raise ValueError('Original authority or camera source missing: ' + name)
        if difference in ('law', 'police_officer', 'official_device'):
            original_direction_record(variant, v, difference, variant_rows)
    return {'format': 'c229410-branch-source-comparison-v1', 'passed': True,
            'difference': difference, 'source_kind': b['source_kind'],
            'fixed_map_sha256': sha(base / 'road.xodr'),
            'fixed_frames_sha256': sha(base / 'video_frames.jsonl'),
            'base_motion_sha256': sha(base / 'native-vehicle.jsonl'),
            'variant_motion_sha256': sha(variant / 'native-vehicle.jsonl'),
            'physical_or_legal_result_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', required=True)
    parser.add_argument('--variant', required=True)
    parser.add_argument('--difference', required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.base, args.variant, args.difference), sort_keys=True))
