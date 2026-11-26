"""Independent original-source comparison of the two opposing passes."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUFFIXES = ('witness_1', 'witness_2')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError('Comparison lacks 600 joined original frames')
    return rows


def requests():
    rows = []
    for suffix in SUFFIXES:
        construction = json.loads((HERE / 'native/bundles' / suffix / 'construction.json').read_text())
        request = next(item['content'] for item in construction['files'] if item['path'] == 'request.jsonl')
        rows.append([json.loads(line) for line in request.splitlines()])
    return rows


def verify_requests(left, right):
    if len(left) != 600 or len(right) != 600:
        raise ValueError('Incomplete requested comparison')
    for index, (a, b) in enumerate(zip(left, right)):
        if a['frame'] != index or b['frame'] != index or a['time_s'] != b['time_s']:
            raise ValueError('Comparison frame/time differs')
        changed = {key for key in set(a) | set(b) if a.get(key) != b.get(key)}
        if changed != {'ego_center_xyz_m', 'requested_ego_lateral_center_y_m'}:
            raise ValueError('Uncontrolled requested comparison')
        if a['ego_center_xyz_m'][0] != b['ego_center_xyz_m'][0] or a['ego_center_xyz_m'][2] != b['ego_center_xyz_m'][2]:
            raise ValueError('Ego route changed outside lateral request')
        if a['ego_center_xyz_m'][1] != -2.0 or b['ego_center_xyz_m'][1] != 1.0:
            raise ValueError('Requested lateral positions changed')
    return True


def verify_source_rows(left, right, tolerance_m=0.25):
    if len(left) != 600 or len(right) != 600:
        raise ValueError('Comparison lacks 600 joined source frames')
    for index, (a, b) in enumerate(zip(left, right)):
        if a.get('video_frame') != index or b.get('video_frame') != index or a.get('time_s') != b.get('time_s'):
            raise ValueError('Source comparison frame/time differs')
        for party in ('ego', 'oncoming'):
            if not all(isinstance(row.get(party, {}).get('center_xyz_m'), list) for row in (a, b)):
                raise ValueError('Both vehicle bodies required for comparison')
            if not all(isinstance(row.get(party, {}).get('body_xyz_m'), list) and len(row[party]['body_xyz_m']) == 8 for row in (a, b)):
                raise ValueError('Both full body extents required for comparison')
        oa, ob = a['oncoming']['center_xyz_m'], b['oncoming']['center_xyz_m']
        ea, eb = a['ego']['center_xyz_m'], b['ego']['center_xyz_m']
        if any(abs(x-y) > tolerance_m for x, y in zip(oa, ob)):
            raise ValueError('Oncoming vehicle changed outside comparison variable')
        if abs(ea[0]-eb[0]) > tolerance_m or abs(ea[2]-eb[2]) > tolerance_m:
            raise ValueError('Ego longitudinal or vertical motion changed')
        if a['ego'].get('velocity_xyz_mps', [None])[0] <= 0 or a['oncoming'].get('velocity_xyz_mps', [None])[0] >= 0 or b['ego'].get('velocity_xyz_mps', [None])[0] <= 0 or b['oncoming'].get('velocity_xyz_mps', [None])[0] >= 0:
            raise ValueError('Opposite-direction motion missing')
    return True


def audit(left_folder, right_folder, output):
    left_folder, right_folder, output = map(Path, (left_folder, right_folder, output))
    if output.exists():
        raise ValueError('Retain previous comparison audit')
    verify_requests(*requests())
    results = []
    for suffix, folder in zip(SUFFIXES, (left_folder, right_folder)):
        result = json.loads((folder / 'result.json').read_text())
        metric = result.get('measured_values', {})
        if result.get('case_id') != HERE.name + '__' + suffix or result.get('provenance_kind') != 'native' or metric.get('source_kind') != 'original_native' or metric.get('diagnostic_fixture') is not False:
            raise ValueError('Original Native comparison source required')
        if not metric.get('source_review_sha256') or sha(folder / 'source-review.json') != metric['source_review_sha256']:
            raise ValueError('Original road and two-body source review missing')
        halves = metric.get('one_half_paved_portion_condition', {})
        if not all(isinstance(halves.get(k), (int, float)) for k in ('minimum_width_available_to_oncoming_m', 'minimum_width_available_to_ego_m')) or halves.get('as_nearly_as_possible') != 'unassessed':
            raise ValueError('Both drivers and unresolved paved-half judgment missing')
        if not result.get('maneuver_completed') or result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met':
            raise ValueError('Original meeting completion missing')
        results.append((result, metric, read_rows(folder / 'native-motion.jsonl')))
    verify_source_rows(results[0][2], results[1][2])
    left_metric, right_metric = results[0][1], results[1][1]
    if left_metric['paved_width_m'] != right_metric['paved_width_m'] or left_metric['first_meeting_frame'] != right_metric['first_meeting_frame']:
        raise ValueError('Paved road or meeting interval changed')
    report = {'format': 'worker-opposing-pass-comparison-audit', 'passed': True,
              'case_ids': [HERE.name + '__' + s for s in SUFFIXES],
              'source_result_sha256': [sha(folder / 'result.json') for folder in (left_folder, right_folder)],
              'fixed_conditions': ['one traffic line each direction', 'paved road width',
                                   'oncoming full body and motion', 'ego longitudinal motion',
                                   '600-frame timeline', 'four source cameras'],
              'deliberate_difference': 'requested_ego_lateral_center_y_m',
              'as_nearly_as_possible': 'unassessed',
              'physical_or_legal_acceptance_claimed_by_fixture': False}
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


def selftest(negative=False):
    verify_requests(*requests())
    rows = []
    for suffix in SUFFIXES:
        path = HERE / 'native/diagnostic' / suffix / 'native-motion.jsonl'
        rows.append(read_rows(path))
    if negative:
        changed = copy.deepcopy(rows[1])
        changed[240]['oncoming']['center_xyz_m'][1] += 1
        verify_source_rows(rows[0], changed)
        raise AssertionError('Changed oncoming body escaped comparison audit')
    verify_source_rows(*rows)
    print(json.dumps({'format': 'worker-opposing-pass-comparison-selftest',
                      'passed': True, 'frames': 600,
                      'case_ids': [HERE.name + '__' + s for s in SUFFIXES],
                      'physical_or_legal_acceptance_claimed': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--left')
    parser.add_argument('--right')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.self_test:
        selftest(args.negative)
    else:
        print(json.dumps(audit(args.left, args.right, args.output)))
