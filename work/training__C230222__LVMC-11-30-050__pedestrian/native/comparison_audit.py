"""Independent source-bound geometry comparison for LVMC 11.30.050.

This reports measured alternatives for review; it does not assign a legal outcome.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(a, b, context_a, context_b, diagnostic=False):
    for report, context, label in ((a, context_a, 'a'), (b, context_b, 'b')):
        require(report['format'] == 'worker-route-geometry-measurement-v1', 'Route report format differs')
        require(report['law_id'] == 'LVMC-11-30-050', 'Wrong law')
        require(report['frames'] == context['expected_frames'] == 600, 'Full crossing frames required')
        require(report['source_context_sha256'] == context['source_sha256'], 'Context source hash differs')
        require(report['legal_verdict'] == 'not_assigned', 'Legal verdict cannot be inferred')
        require(report['source_kind'] == context['source_kind'], 'Source kind differs')
        require(not context['crosswalk_polygons_xy_m'] and report['crosswalk_sample_count'] == 0,
                'Outside-crosswalk fixed condition differs')
        require(report['entry_distance_to_origin_curb_m'] <= 0.75, 'Entry did not reach origin curb')
        require(report['exit_distance_to_opposite_curb_m'] <= 0.75, 'Exit did not reach opposite curb')
        require(report['source_samples_sha256'], 'Source samples absent: ' + label)
        if not diagnostic:
            require(report['source_kind'] == 'native_observation', 'Original Native route source required')
            require(context.get('original_map_and_pixel_reviewed') is True,
                    'Independent original map and pixel review required')
            require(context.get('frame_map_and_camera_decode_reviewed') is True,
                    'Original frame and four-camera review required')
    for key in ('origin_curb_xy_m', 'opposite_curb_xy_m', 'road_geometry_sha256',
                'crosswalk_polygons_xy_m', 'expected_frames'):
        require(context_a[key] == context_b[key], 'Fixed road/curb/crosswalk condition differs: ' + key)
    require(math.dist(a['entry_xy_m'], b['entry_xy_m']) <= 0.25,
            'Compared entries differ')
    require(a['right_angle_deviation_deg'] < b['right_angle_deviation_deg'],
            'Declared route geometry difference absent')
    require(a['route_excess_length_m'] < b['route_excess_length_m'],
            'Declared route length difference absent')
    return {'format': 'worker-route-comparison-audit-v1', 'passed': True,
            'diagnostic': diagnostic, 'legal_verdict': 'not_assigned',
            'fixed_conditions': ['law', 'road', 'curbs', 'crosswalk absence',
                                 'entry', 'duration', 'source schema'],
            'measured_differences': {
                'right_angle_deviation_deg': [a['right_angle_deviation_deg'], b['right_angle_deviation_deg']],
                'route_excess_length_m': [a['route_excess_length_m'], b['route_excess_length_m']]}}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--a', type=Path, required=True)
    p.add_argument('--b', type=Path, required=True)
    p.add_argument('--context-a', type=Path, required=True)
    p.add_argument('--context-b', type=Path, required=True)
    p.add_argument('--diagnostic', action='store_true')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    a, b = json.loads(args.a.read_text()), json.loads(args.b.read_text())
    ca, cb = json.loads(args.context_a.read_text()), json.loads(args.context_b.read_text())
    ca['source_sha256'], cb['source_sha256'] = sha(args.context_a), sha(args.context_b)
    result = audit(a, b, ca, cb, args.diagnostic)
    result['sources'] = {str(path): sha(path) for path in
                         (args.a, args.b, args.context_a, args.context_b)}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
