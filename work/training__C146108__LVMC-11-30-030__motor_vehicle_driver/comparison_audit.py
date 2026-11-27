"""Independent crosswalk-kind and pass-policy comparison audit."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from crosswalk_pass_scene import request

HERE = Path(__file__).resolve().parent
AID = HERE.name
PAIRS = {
    AID + '__marked_pass_contrast': ('false', 'true', 'pass_policy'),
    AID + '__unmarked_intersection_pass_contrast': ('unmarked_false', 'unmarked_true', 'pass_policy'),
    AID + '__false_crosswalk_kind_contrast': ('false', 'unmarked_false', 'crosswalk_kind'),
    AID + '__true_crosswalk_kind_contrast': ('true', 'unmarked_true', 'crosswalk_kind')}
CAMERAS = {'overview', 'approach', 'reference_corner', 'driver_reference'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    result = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if len(result) != 600:
        raise ValueError('Comparison lacks full 600-frame source')
    return result


def verify_requests(first, second, variable):
    a, b = request(first), request(second)
    fixed = ('ego', 'lead_vehicle', 'pedestrian', 'cameras', 'rate_hz',
             'duration_s', 'planned_frames', 'weather')
    for key in fixed:
        if a.get(key) != b.get(key):
            raise ValueError('Fixed actor, weather or camera request changed: ' + key)
    if variable == 'pass_policy':
        if a['road_opendrive'] != b['road_opendrive'] or a['controller'] == b['controller']:
            raise ValueError('Declared pass-policy contrast missing or road changed')
    else:
        if a['controller'] != b['controller'] or a['road_opendrive'] == b['road_opendrive']:
            raise ValueError('Declared crossing-kind contrast missing or controller changed')


def compare_sources(first, second, variable):
    if len(first) != 600 or len(second) != 600:
        raise ValueError('Full original motion source missing')
    for group in (first, second):
        previous = None
        for i, row in enumerate(group):
            if (row.get('video_frame') != i or row.get('source_cameras') != {name: i for name in CAMERAS}
                    or abs(row.get('time_s', -1) - i / 20) > 1e-6
                    or type(row.get('native_frame')) is not int
                    or (previous is not None and row['native_frame'] <= previous)):
                raise ValueError('Original frame or camera join differs')
            previous = row['native_frame']
    if variable == 'pass_policy':
        if not any(a['ego_x_m'] != b['ego_x_m'] or a['ego_y_m'] != b['ego_y_m']
                   for a, b in zip(first, second)):
            raise ValueError('Measured pass-policy trajectory contrast absent')
    else:
        if any(a['ego_x_m'] != b['ego_x_m'] or a['ego_y_m'] != b['ego_y_m']
               for a, b in zip(first, second)):
            raise ValueError('Fixed pass-policy trajectory request changed')
    return {'source_frames_per_case': 600, 'variable': variable,
            'physical_crossing_and_pass': 'original_review_required',
            'legal_result': None}


def audit(comparison, attempts, output):
    if comparison not in PAIRS or len(attempts) != 2:
        raise ValueError('Exact comparison membership differs')
    first, second, variable = PAIRS[comparison]
    verify_requests(first, second, variable)
    histories, sources, measures = [], [], []
    for slug, folder in zip((first, second), map(Path, attempts)):
        result_path = folder / 'result.json'
        result = read(result_path)
        if (result.get('case_id') != AID + '__' + slug
                or result.get('provenance_kind') != 'native'
                or result.get('diagnostic_fixture') is not False
                or result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met'):
            raise ValueError('Original Native physical source missing: ' + slug)
        crossing = read(folder / 'crosswalk-review.json')
        purpose = read(folder / 'purpose-review.json')
        if (crossing.get('diagnostic_fixture_only') or purpose.get('diagnostic_fixture_only')
                or crossing.get('source_kind') != 'independent_original_crosswalk_review'
                or purpose.get('source_kind') != 'independent_original_stop_purpose_review'
                or crossing.get('reviewer') == purpose.get('reviewer')
                or purpose.get('lead_stopped_for_pedestrian_sourced') is not True):
            raise ValueError('Independent original crossing and stop-purpose review missing')
        kind = 'unmarked_intersection' if slug.startswith('unmarked') else 'marked'
        if crossing.get('crosswalk_kind') != kind:
            raise ValueError('Original crossing kind differs')
        motion = folder / 'crosswalk_trace.jsonl'
        histories.append(rows(motion))
        measures.append(result.get('measured_values', {}))
        sources.append({'result': sha(result_path), 'motion': sha(motion),
                        'road': sha(folder / 'road.xodr'),
                        'crossing': sha(folder / 'crosswalk-review.json'),
                        'purpose': sha(folder / 'purpose-review.json')})
    measured = compare_sources(*histories, variable)
    if variable == 'pass_policy':
        if sources[0]['road'] != sources[1]['road'] or measures[0].get('pass_observed') == measures[1].get('pass_observed'):
            raise ValueError('Original pass contrast absent or road changed')
    else:
        if sources[0]['road'] == sources[1]['road'] or measures[0].get('pass_observed') != measures[1].get('pass_observed'):
            raise ValueError('Crossing-kind contrast changed pass outcome or road did not change')
    report = {'format': 'worker-crosswalk-comparison-audit', 'passed': True,
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
    groups = [rows(HERE / 'diagnostic' / slug / 'sources/crosswalk_trace.jsonl')
              for slug in (first, second)]
    if negative:
        groups = copy.deepcopy(groups)
        groups[1][250]['source_cameras'].pop('approach')
        compare_sources(*groups, variable)
        raise AssertionError('Changed camera identity unexpectedly accepted')
    measured = compare_sources(*groups, variable)
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
