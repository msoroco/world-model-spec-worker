"""Independent source-bound departure pair audit; leaves statutory judgment open."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def _load(path):
    p = Path(path)
    if not p.is_file():
        raise ValueError('measurement report missing')
    return json.loads(p.read_text())


def _verified_source(source):
    path = Path(source['path'])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
        raise ValueError('comparison source missing or hash differs')


def _original_approach(report):
    trace = _load(report['sources'][1]['path'])
    if trace.get('case_id') != report['case_id']:
        raise ValueError('comparison original trace case differs')
    samples = trace.get('samples')
    if not isinstance(samples, list):
        raise ValueError('comparison original approach samples missing')
    approach = []
    for sample in samples:
        if sample.get('phase') == 'intersection_entry':
            break
        if sample.get('phase') != 'approach' or sample.get('road_id') != report['approach_road_id']:
            raise ValueError('comparison original approach phase or road differs')
        xy = sample.get('position_xy_m')
        heading, speed = sample.get('heading_rad'), sample.get('speed_mps')
        if (not isinstance(xy, list) or len(xy) != 2 or
                any(type(x) not in (int, float) or not math.isfinite(x) for x in xy) or
                any(type(x) not in (int, float) or not math.isfinite(x) for x in (heading, speed)) or speed < 0):
            raise ValueError('comparison original approach measurement invalid')
        approach.append((xy, heading, speed))
    if len(approach) < 2 or len(approach) == len(samples):
        raise ValueError('comparison original approach or intersection entry missing')
    return approach


def audit(near_report, far_report, *, expected_near, expected_far, expected_centerline_kind):
    """Check measured pair isolation without a legal position threshold."""
    near = _load(near_report)
    far = _load(far_report)
    for report, expected in ((near, expected_near), (far, expected_far)):
        if report.get('case_id') != expected:
            raise ValueError('comparison case identity differs')
        if report.get('centerline_kind') != expected_centerline_kind:
            raise ValueError('comparison centerline convention differs')
        if report.get('statutory_position_judgment') is not None:
            raise ValueError('comparison cannot carry legal judgment')
        if report.get('sample_count', 0) < 1 or not report.get('per_frame'):
            raise ValueError('comparison original departure samples missing')
        if len(report.get('sources', [])) != 2:
            raise ValueError('comparison map and trace sources required')
        for source in report['sources']:
            _verified_source(source)
        if not all(math.isfinite(report.get(key, float('nan'))) for key in ('observed_right_min_m', 'observed_right_max_m')):
            raise ValueError('comparison measurements non-finite')
        if report['observed_right_min_m'] > report['observed_right_max_m']:
            raise ValueError('comparison range inverted')
    for key in ('approach_road_id', 'destination_road_id'):
        if near.get(key) != far.get(key):
            raise ValueError('comparison road connection changed')
    if near['sources'][0]['sha256'] != far['sources'][0]['sha256']:
        raise ValueError('comparison fixed map source changed')
    if near['sources'][1]['sha256'] == far['sources'][1]['sha256']:
        raise ValueError('comparison trace source reused')
    near_approach, far_approach = _original_approach(near), _original_approach(far)
    if len(near_approach) != len(far_approach):
        raise ValueError('comparison fixed approach duration changed')
    for first, second in zip(near_approach, far_approach):
        if (math.dist(first[0], second[0]) > .25 or
                abs(math.remainder(first[1] - second[1], 2 * math.pi)) > .1 or
                abs(first[2] - second[2]) > .5):
            raise ValueError('comparison original approach trajectory changed')
    if near['observed_right_min_m'] >= far['observed_right_min_m']:
        raise ValueError('farther case did not measure farther from centerline')
    return {
        'case_ids':[expected_near, expected_far],
        'measured_lateral_order':'farther_target_has_greater_observed_right_min',
        'near_right_min_m':near['observed_right_min_m'],
        'far_right_min_m':far['observed_right_min_m'],
        'fixed_map_source_sha256':near['sources'][0]['sha256'],
        'original_trace_sources':[near['sources'][1]['sha256'],far['sources'][1]['sha256']],
        'fixed_approach_samples': len(near_approach),
        'fixed_approach_tolerances': {'position_m': .25, 'heading_rad': .1, 'speed_mps': .5},
        'statutory_judgment':None,
        'limitations':['Engineering approach tolerances are comparison controls, not statutory position thresholds.', 'Original full-video visibility requires separate audit.'],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--near-report', required=True)
    parser.add_argument('--far-report', required=True)
    parser.add_argument('--expected-near', required=True)
    parser.add_argument('--expected-far', required=True)
    parser.add_argument('--centerline-kind', choices=['mapped', 'source_derived_imaginary'], required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.near_report, args.far_report,
                   expected_near=args.expected_near,
                   expected_far=args.expected_far,
                   expected_centerline_kind=args.centerline_kind)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
