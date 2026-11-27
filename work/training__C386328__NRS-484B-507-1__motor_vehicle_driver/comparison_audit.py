"""Independent fixed-source and declared-difference audit for freight-zone pairs."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from freight_scene import scene_request

HERE = Path(__file__).resolve().parent
AID = HERE.name
PAIRS = {
    AID + '__comparison': ('probe_1', 'probe_2', 'material_activity'),
    AID + '__signed_hours_contrast': ('probe_2', 'probe_3', 'signed_hours'),
    AID + '__passenger_exchange_contrast': ('probe_2', 'probe_4', 'passenger_exchange'),
    AID + '__waiting_material_vehicle_contrast': ('probe_4', 'probe_5', 'waiting_material_vehicle')}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    value = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if len(value) != 600:
        raise ValueError('Comparison lacks full 600-frame source')
    return value


def verify_requests(first, second, variable):
    a, b = scene_request(first), scene_request(second)
    for key in ('road_opendrive', 'vehicle', 'zone', 'sign', 'cameras',
                'rate_hz', 'duration_s', 'planned_frames'):
        if a[key] != b[key]:
            raise ValueError('Fixed road, vehicle, sign or camera request changed')
    allowed = {'material_activity': {'material'},
               'signed_hours': {'civil_time'},
               'passenger_exchange': {'passenger'},
               'waiting_material_vehicle': {'material_transport_vehicle'}}[variable]
    for key in ('material', 'civil_time', 'passenger', 'material_transport_vehicle'):
        if key in allowed:
            if a[key] == b[key]:
                raise ValueError('Declared request contrast absent: ' + variable)
        elif a[key] != b[key]:
            raise ValueError('Undeclared request difference: ' + key)


def compare_rows(first, second, variable):
    if len(first) != 600 or len(second) != 600:
        raise ValueError('Full comparison sources missing')
    for i, (a, b) in enumerate(zip(first, second)):
        if (a.get('video_frame') != b.get('video_frame') or a.get('video_frame') != i
                or a.get('native_frame') != b.get('native_frame')
                or abs(a.get('time_s', -1) - b.get('time_s', -2)) > 1e-6
                or a.get('vehicle_id') != b.get('vehicle_id')
                or a.get('vehicle_xyz_m') != b.get('vehicle_xyz_m')
                or a.get('observed_speed_mps') != b.get('observed_speed_mps')
                or a.get('source_cameras') != b.get('source_cameras')):
            raise ValueError('Fixed original actor, road motion or source clock changed')
        if variable != 'signed_hours' and a.get('civil_timestamp') != b.get('civil_timestamp'):
            raise ValueError('Fixed original civil time changed')
        if variable != 'material_activity' and a.get('material_xyz_m') != b.get('material_xyz_m'):
            raise ValueError('Fixed original material position changed')
        if variable != 'passenger_exchange' and a.get('passenger_xyz_m') != b.get('passenger_xyz_m'):
            raise ValueError('Fixed original passenger position changed')
        if variable != 'waiting_material_vehicle' and a.get('waiting_vehicle_xyz_m') != b.get('waiting_vehicle_xyz_m'):
            raise ValueError('Fixed original waiting vehicle position changed')
    key = {'material_activity': 'material_xyz_m',
           'signed_hours': 'civil_timestamp',
           'passenger_exchange': 'passenger_xyz_m',
           'waiting_material_vehicle': 'waiting_vehicle_xyz_m'}[variable]
    if not any(a[key] != b[key] for a, b in zip(first, second)):
        raise ValueError('Measured source contrast absent: ' + variable)
    return {'variable': variable, 'source_frames': 600,
            'original_source_difference_observed': True,
            'expeditiousness': 'unassessed',
            'physical_interference': 'independent_original_review_required',
            'legal_result': None}


def audit(comparison, attempts, output):
    if comparison not in PAIRS or len(attempts) != 2:
        raise ValueError('Exact comparison membership differs')
    first, second, variable = PAIRS[comparison]
    verify_requests(first, second, variable)
    sources, histories = [], []
    for slug, folder in zip((first, second), map(Path, attempts)):
        result_path = folder / 'result.json'
        result = read(result_path)
        if (result.get('case_id') != AID + '__' + slug
                or result.get('provenance_kind') != 'native'
                or result.get('diagnostic_fixture') is not False
                or result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met'):
            raise ValueError('Original Native physical source missing: ' + slug)
        zone, activity = read(folder / 'zone-review.json'), read(folder / 'activity-review.json')
        if (zone.get('diagnostic_fixture_only') or activity.get('diagnostic_fixture_only')
                or zone.get('source_kind') != 'independent_original_zone_review'
                or activity.get('source_kind') != 'independent_original_activity_review'
                or zone.get('reviewer') == activity.get('reviewer')):
            raise ValueError('Independent original zone/activity review missing')
        motion = folder / 'freight_trace.jsonl'
        histories.append(rows(motion))
        sources.append({'result': sha(result_path), 'motion': sha(motion),
                        'road': sha(folder / 'road.xodr'),
                        'zone': sha(folder / 'zone-review.json'),
                        'activity': sha(folder / 'activity-review.json')})
    if sources[0]['road'] != sources[1]['road']:
        raise ValueError('Fixed original road source changed')
    measured = compare_rows(*histories, variable)
    report = {'format': 'worker-freight-zone-comparison-audit', 'passed': True,
              'comparison_id': comparison, 'case_ids': [AID + '__' + first, AID + '__' + second],
              'source_sha256': sources, 'measurement': measured,
              'deliberate_differences': [variable], 'original_legal_judgment': 'pending'}
    path = Path(output)
    if path.exists():
        raise ValueError('Retain previous comparison audit')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


def selftest(comparison, negative):
    first, second, variable = PAIRS[comparison]
    verify_requests(first, second, variable)
    groups = [rows(HERE / 'diagnostic' / slug / 'sources/freight_trace.jsonl')
              for slug in (first, second)]
    if negative:
        groups = copy.deepcopy(groups)
        groups[1][250]['vehicle_id'] += 10
        compare_rows(*groups, variable)
        raise AssertionError('Changed original actor identity unexpectedly accepted')
    measured = compare_rows(*groups, variable)
    print(json.dumps({'comparison_id': comparison, 'cpu_predicates_passed': True,
                      'measurement': measured, 'original_acquisition_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', choices=tuple(PAIRS), required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--attempt', action='append')
    parser.add_argument('--output')
    args = parser.parse_args()
    selftest(args.comparison, args.negative) if args.self_test else audit(args.comparison, args.attempt or [], args.output)
