"""Independent exact source comparison for distance, interruption, rain and side."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from delivery_audit import check_result, check_review
from measure_signal import measure
from signal_scene import request

HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    value = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if len(value) != 600:
        raise ValueError('Comparison lacks full 600-frame source')
    return value


def comparison(comparison_id):
    plan = read(HERE / 'case-plan.json')
    matches = [row for row in plan['comparisons'] if row['comparison_id'] == comparison_id]
    if len(matches) != 1:
        raise ValueError('Unknown exact comparison')
    item = matches[0]
    suffixes = [case.rsplit('__', 1)[-1] for case in item['case_ids']]
    kind = comparison_id.rsplit('__', 1)[-1]
    return item, suffixes, kind


def verify_requests(suffixes, kind):
    plans = [request(s) for s in suffixes]
    fixed = ('course_change_request_odometer_m', 'speed_request_mps', 'frames',
             'rate_hz', 'duration_s', 'maneuver', 'layout', 'control')
    if any(any(plan[key] != plans[0][key] for key in fixed) for plan in plans[1:]):
        raise ValueError('Fixed actor, road, clock or course request changed')
    if kind.endswith('boundary'):
        if len(plans) != 3 or len({p['requested_signal_distance_ft'] for p in plans}) != 3:
            raise ValueError('Boundary distance contrast missing')
        if len({p['area_class_requested'] for p in plans}) != 1:
            raise ValueError('Boundary mixes legal district classes')
    elif kind.endswith('interrupt_contrast'):
        if len(plans) != 2 or [p['interruption_requested'] for p in plans] != [False, True]:
            raise ValueError('Signal interruption contrast missing')
    elif kind.endswith('rain_contrast'):
        if len(plans) != 2 or [p['weather_requested'] for p in plans] != ['clear', 'rain']:
            raise ValueError('Weather contrast missing')
    elif kind.endswith('right_contrast'):
        if len(plans) != 2 or [p['signal_side'] for p in plans] != ['left', 'right']:
            raise ValueError('Signal-side contrast missing')
    else:
        raise ValueError('Unknown comparison branch')
    return plans


def compare_sources(groups, contexts, kind, area_class):
    measurements = [measure(group, area_class) for group in groups]
    for group in groups:
        if [row.get('frame') for row in group] != list(range(600)):
            raise ValueError('Comparison original frame identity differs')
    if any(abs(a['time_s'] - b['time_s']) > 1e-6
           for group in groups[1:] for a, b in zip(groups[0], group)):
        raise ValueError('Fixed source clock changed')
    values = [m['observed_continuous_distance_ft'] for m in measurements]
    if kind.endswith('boundary'):
        if len(values) != 3 or not values[0] < values[1] < values[2]:
            raise ValueError('Measured distance boundary contrast absent')
    elif kind.endswith('interrupt_contrast'):
        if not values[1] < values[0]:
            raise ValueError('Measured signal interruption absent')
    elif kind.endswith('rain_contrast'):
        rain = [c['weather_source']['measurement']['precipitation_max'] for c in contexts]
        if not rain[0] < rain[1] or abs(values[0] - values[1]) > 1:
            raise ValueError('Weather-only source contrast absent')
    elif kind.endswith('right_contrast'):
        directions = [group[measurements[i]['event_frame']]['turn_indicator'] for i, group in enumerate(groups)]
        if directions != ['left', 'right'] or abs(values[0] - values[1]) > 1:
            raise ValueError('Signal-side-only contrast absent')
    return {'observed_continuous_distance_ft': values,
            'threshold_ft': measurements[0]['threshold_ft'],
            'area_class': area_class, 'legal_judgment': 'pending'}


def audit(item, suffixes, kind, attempts, output):
    if len(attempts) != len(suffixes):
        raise ValueError('Exact comparison membership differs')
    groups, contexts, sources, classes = [], [], [], []
    for suffix, folder in zip(suffixes, map(Path, attempts)):
        case = AID + '__' + suffix
        result = read(folder / 'result.json')
        check_result(result, case)
        review = read(folder / 'original-review.json')
        check_review(review, case)
        area = review.get('district_class')
        if area not in ('business_or_residential', 'other'):
            raise ValueError('Original district class finding missing')
        classes.append(area)
        for name, checksum in review['source_sha256'].items():
            if sha(folder / name) != checksum:
                raise ValueError('Reviewed original comparison source changed')
        groups.append(rows(folder / 'signal-source.jsonl'))
        contexts.append(read(folder / 'source-context.json'))
        sources.append({'result_sha256': sha(folder / 'result.json'),
                        'signal_sha256': sha(folder / 'signal-source.jsonl'),
                        'review_sha256': sha(folder / 'original-review.json'),
                        'road_sha256': sha(folder / 'road.xodr')})
    if len(set(classes)) != 1 or len({s['road_sha256'] for s in sources}) != 1:
        raise ValueError('Original area class or road changed within comparison')
    measured = compare_sources(groups, contexts, kind, classes[0])
    report = {'format': 'worker-signal-distance-comparison-audit', 'passed': True,
              'comparison_id': item['comparison_id'], 'case_ids': item['case_ids'],
              'source_sha256': sources, 'measurement': measured,
              'legal_verdict': 'unassessed_pending_original_review'}
    target = Path(output)
    if target.exists():
        raise ValueError('Retain prior comparison audit')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


def selftest(item, suffixes, kind, negative):
    verify_requests(suffixes, kind)
    groups = [rows(HERE / 'fixture-source' / s / 'signal-source.jsonl') for s in suffixes]
    contexts = [{'weather_source': {'measurement': {'precipitation_max':
        max(json.loads(line)['world']['weather']['precipitation'] for line in
            (HERE / 'fixture-source' / s / 'capture/evidence.jsonl').read_text().splitlines())}}}
        for s in suffixes]
    if negative:
        groups = copy.deepcopy(groups)
        groups[1][250]['frame'] += 1
        compare_sources(groups, contexts, kind, request(suffixes[0])['area_class_requested'])
        raise AssertionError('Changed source frame unexpectedly accepted')
    measured = compare_sources(groups, contexts, kind, request(suffixes[0])['area_class_requested'])
    print(json.dumps({'comparison_id': item['comparison_id'], 'cpu_predicates_passed': True,
                      'measurement': measured, 'original_acquisition_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--attempt', action='append')
    parser.add_argument('--output')
    args = parser.parse_args()
    item, suffixes, kind = comparison(args.comparison)
    if args.self_test:
        selftest(item, suffixes, kind, args.negative)
    else:
        audit(item, suffixes, kind, args.attempt or [], args.output)
