"""Independent pass-geometry comparison; CPU fixtures prove predicates only."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
GROUPS = {'witness_comparison': ('witness_1', 'witness_2'),
          'exception_1_comparison': ('exception_1_1', 'exception_1_2'),
          'numeric_1_comparison': ('numeric_1_0', 'numeric_1_1', 'numeric_1_2'),
          'return_order_comparison': ('ordering_1', 'ordering_2')}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    value = [json.loads(line) for line in Path(path).read_text().splitlines()]
    if len(value) != 600:
        raise ValueError('Comparison lacks 600 source frames')
    for index, row in enumerate(value):
        if row.get('video_frame') != index or abs(row.get('time_s', -999) - index / 20) > .001:
            raise ValueError('Comparison frame/time source changed')
        if not all(k in row for k in ('ego', 'scooter', 'authored_center_marking')):
            raise ValueError('Comparison participant/road source missing')
    return value


def check(group, sources):
    if group not in GROUPS or len(sources) != len(GROUPS[group]):
        raise ValueError('Comparison membership differs')
    first = sources[0]
    markings = []
    gaps = []
    returns = []
    for source in sources:
        markings.append(source[0]['authored_center_marking'])
        gaps.append(min(row['ego']['center_xy_m'][1] - row['scooter']['center_xy_m'][1]
                        for row in source[170:230]))
        returns.append(next((index for index in range(101, len(source))
                             if source[index]['ego']['center_xy_m'][1] <
                             source[index - 1]['ego']['center_xy_m'][1] - 1e-8), 600))
        for row in source:
            if row['scooter']['blueprint_id'] != first[0]['scooter']['blueprint_id']:
                raise ValueError('Fixed surveyed scooter blueprint changed')
    for source in sources[1:]:
        for a, b in zip(first, source):
            for part in ('ego', 'scooter'):
                if a[part]['center_xy_m'][0] != b[part]['center_xy_m'][0]:
                    raise ValueError('Fixed longitudinal trajectory changed')
            if a['scooter']['center_xy_m'] != b['scooter']['center_xy_m']:
                raise ValueError('Fixed surveyed rider trajectory changed')
    if group == 'exception_1_comparison':
        if markings != ['broken', 'solid'] or any(a['ego']['center_xy_m'] != b['ego']['center_xy_m']
                                                   for a, b in zip(*sources)):
            raise ValueError('Center/no-passing context not isolated')
    else:
        if len(set(markings)) != 1:
            raise ValueError('Fixed center marking changed')
    if group == 'return_order_comparison':
        if not returns[0] < returns[1]:
            raise ValueError('Return ordering did not differ')
    elif group != 'exception_1_comparison':
        if len(set(round(gap, 6) for gap in gaps)) != len(gaps):
            raise ValueError('Requested lateral gap did not differ')
    return {'case_ids': [HERE.name + '__' + suffix for suffix in GROUPS[group]],
            'source_frame_count': 600, 'markings': markings,
            'sampled_lateral_center_offsets_m': gaps, 'return_frames': returns,
            'legal_or_original_completion_claimed': False}


def selftest(group, negative):
    sources = [rows(HERE / 'diagnostic' / suffix / 'sources' / 'participant-poses.jsonl')
               for suffix in GROUPS[group]]
    if negative:
        sources = copy.deepcopy(sources)
        sources[-1][300]['scooter']['center_xy_m'][0] += 2
        check(group, sources)
        raise AssertionError('Changed fixed rider trajectory accepted')
    print(json.dumps({'format': 'c272412-comparison-cpu', 'comparison': group,
                      'passed': True, **check(group, sources)}))


def audit(group, attempts, output):
    if len(attempts) != len(GROUPS[group]):
        raise ValueError('Exact original attempts required')
    source_rows = []
    digests = []
    rider_sources = []
    for suffix, attempt in zip(GROUPS[group], map(Path, attempts)):
        result = read(attempt / 'result.json')
        metric = result.get('measured_values', {})
        if result.get('case_id') != HERE.name + '__' + suffix or metric.get('original_native_observed') is not True or metric.get('source_kind') != 'native_original':
            raise ValueError('Exact original Native comparison source required')
        if not result.get('maneuver_completed') or result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met':
            raise ValueError('Original physical pass completion missing')
        source = attempt / 'participant-poses.jsonl'
        if sha(source) != metric.get('source_sha256', {}).get(source.name):
            raise ValueError('Original rider/driver source hash differs')
        if group == 'exception_1_comparison':
            road = ET.fromstring((attempt / 'road.xodr').read_text())
            geometry = road.find('road/planView/geometry')
            if (geometry is None or 'y' not in geometry.attrib or
                    not math.isfinite(float(geometry.attrib['y'])) or abs(float(geometry.attrib['y'])) > 1e-5):
                raise ValueError('Original road center reference differs')
            context = read(attempt / 'pass-context.json')
            survey_path = Path(context.get('survey_path', ''))
            if not survey_path.is_file() or sha(survey_path) != context.get('survey_sha256'):
                raise ValueError('Original exception survey binding differs')
            survey = read(survey_path)
            if not survey.get('cited_213_217_applicability_source'):
                raise ValueError('Original NRS 484B.213/.217 source missing')
            if (not survey.get('no_passing_zone_source') or
                    survey.get('no_passing_zone_designated') is not (suffix == 'exception_1_2')):
                raise ValueError('Original case-specific no-passing-zone designation source missing')
            if not any(max(point[1] for point in row['ego']['body_xy_m']) > 0
                       for row in rows(source)[metric['first_abreast_frame']:metric['last_abreast_frame'] + 1]):
                raise ValueError('Original centerline crossing geometry missing')
        else:
            context = read(attempt / 'pass-context.json')
            survey_path = Path(context.get('survey_path', ''))
            if not survey_path.is_file() or sha(survey_path) != context.get('survey_sha256'):
                raise ValueError('Original rider survey binding differs')
            survey = read(survey_path)
        rider_sources.append(survey.get('rider_identity_source'))
        source_rows.append(rows(source))
        digests.append(sha(source))
    if not rider_sources[0] or len(set(rider_sources)) != 1:
        raise ValueError('Fixed original rider identity source differs')
    checked = check(group, source_rows)
    value = {'format': 'c272412-original-comparison-audit', 'passed': True,
             'comparison_id': HERE.name + '__' + group,
             'source_sha256': digests, **checked}
    path = Path(output)
    if path.exists():
        raise ValueError('Retain prior original audit')
    path.write_text(json.dumps(value, indent=2) + '\n')
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', choices=GROUPS, required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--attempt', action='append')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.self_test:
        selftest(args.comparison, args.negative)
    else:
        print(json.dumps(audit(args.comparison, args.attempt, args.output)))
