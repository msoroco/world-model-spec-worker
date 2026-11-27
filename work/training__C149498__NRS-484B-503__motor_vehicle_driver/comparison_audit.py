"""Independent exact-pair audit of passenger request, sign-hour and action contrasts."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from native.loading_scene import request

HERE = Path(__file__).resolve().parent
AID = HERE.name
PREFIX = AID + '__selected_bae4893e__'
PAIRS = {
    PREFIX + 'comparison': ('condition_a', 'condition_b', 'actual_passenger_loading'),
    PREFIX + 'signed_hours_loading_comparison': ('condition_a', 'outside_hours_loading', 'signed_effective_hours'),
    PREFIX + 'signed_hours_no_transfer_comparison': ('condition_b', 'outside_hours_no_transfer', 'signed_effective_hours'),
    PREFIX + 'action_duration_comparison': ('brief_stop_no_transfer', 'extended_park_no_transfer', 'action_and_measured_duration')}


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
    a, b = request(first), request(second)
    for key in ('road_opendrive', 'ego', 'cameras', 'rate_hz', 'duration_s', 'planned_frames'):
        if a[key] != b[key]:
            raise ValueError('Fixed road, ego, camera or clock request changed')
    if variable == 'actual_passenger_loading':
        if (a['zone'] != b['zone'] or a['controller'] != b['controller']
                or a['passenger']['cross_doorway_requested'] is not True
                or b['passenger']['cross_doorway_requested'] is not False):
            raise ValueError('Passenger-only controlled request differs')
    elif variable == 'signed_effective_hours':
        if (a['controller'] != b['controller'] or a['passenger'] != b['passenger']
                or a['zone']['civil_timestamp_start'] == b['zone']['civil_timestamp_start']
                or {k: v for k, v in a['zone'].items() if k != 'civil_timestamp_start'} !=
                   {k: v for k, v in b['zone'].items() if k != 'civil_timestamp_start'}):
            raise ValueError('Signed-hours-only controlled request differs')
    elif variable == 'action_and_measured_duration':
        if (a['zone'] != b['zone'] or a['passenger'] != b['passenger']
                or a['controller']['action_request'] != 'brief_stop'
                or b['controller']['action_request'] != 'extended_park'
                or a['controller']['resume_request_frame'] >= b['controller']['resume_request_frame']):
            raise ValueError('Action-duration controlled request differs')
    else:
        raise ValueError('Unknown exact comparison variable')


def compare_rows(first, second, variable):
    if len(first) != 600 or len(second) != 600:
        raise ValueError('Full comparison sources missing')
    for i, (a, b) in enumerate(zip(first, second)):
        if (a.get('video_frame') != i or b.get('video_frame') != i
                or a.get('native_frame') != b.get('native_frame')
                or abs(a.get('time_s', -1) - b.get('time_s', -2)) > 1e-6
                or a.get('ego_actor_id') != b.get('ego_actor_id')
                or a.get('passenger_actor_id') != b.get('passenger_actor_id')):
            raise ValueError('Fixed actor or source clock changed')
        if variable != 'signed_effective_hours' and a.get('civil_timestamp') != b.get('civil_timestamp'):
            raise ValueError('Fixed civil time changed')
        if variable != 'action_and_measured_duration' and a.get('vehicle_speed_mps') != b.get('vehicle_speed_mps'):
            raise ValueError('Fixed vehicle motion changed')
    if variable == 'signed_effective_hours':
        if first[0]['civil_timestamp'] == second[0]['civil_timestamp']:
            raise ValueError('Signed-hour source contrast absent')
    elif variable == 'actual_passenger_loading':
        if first[260]['passenger_center_m'] == second[260]['passenger_center_m']:
            raise ValueError('Passenger movement contrast absent')
    else:
        first_halt = sum(r['vehicle_speed_mps'] <= .05 for r in first)
        second_halt = sum(r['vehicle_speed_mps'] <= .05 for r in second)
        if not first_halt < second_halt:
            raise ValueError('Action duration source contrast absent')
    return {'variable': variable, 'source_frames': 600,
            'first_halt_frames': sum(r['vehicle_speed_mps'] <= .05 for r in first),
            'second_halt_frames': sum(r['vehicle_speed_mps'] <= .05 for r in second),
            'legal_expeditiousness': 'unassessed'}


def audit(comparison, attempts, output):
    if len(attempts) != 2:
        raise ValueError('Exact comparison membership differs')
    first, second, variable = PAIRS[comparison]
    verify_requests(first, second, variable)
    sources = []
    histories = []
    for slug, folder in zip((first, second), map(Path, attempts)):
        result_path = folder / 'result.json'
        result = read(result_path)
        if (result.get('case_id') != PREFIX + slug or result.get('provenance_kind') != 'native'
                or result.get('diagnostic_fixture') is not False
                or result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met'):
            raise ValueError('Original Native physical source missing: ' + slug)
        context = read(folder / 'loading_context.json')
        if (context.get('source_kind') != 'original_native_passenger_curb_readback'
                or context.get('regulatory_authority_confirmed') is not False):
            raise ValueError('Original loading context or authority state differs')
        motion = folder / 'loading_motion.jsonl'
        histories.append(rows(motion))
        sources.append({'result': sha(result_path), 'motion': sha(motion),
                        'road': sha(folder / 'road.xodr'), 'sign': sha(folder / 'loading_zone.json')})
    if sources[0]['road'] != sources[1]['road']:
        raise ValueError('Fixed road source changed')
    if variable != 'signed_effective_hours' and sources[0]['sign'] != sources[1]['sign']:
        raise ValueError('Fixed sign source changed')
    measured = compare_rows(*histories, variable)
    report = {'format': 'worker-passenger-curb-comparison-audit', 'passed': True,
              'comparison_id': comparison, 'case_ids': [PREFIX + first, PREFIX + second],
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
    groups = [rows(HERE / 'selected-source' / slug / 'loading_motion.jsonl') for slug in (first, second)]
    if negative:
        groups = copy.deepcopy(groups)
        groups[1][250]['ego_actor_id'] += 10
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
