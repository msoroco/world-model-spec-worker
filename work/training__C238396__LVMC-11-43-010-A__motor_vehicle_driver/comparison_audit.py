"""Independent source comparison of exact opposite roundabout directions."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'native'))
from finalize import analyze, rows


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(attempt_a, attempt_b, processing_a, processing_b, diagnostic=False):
    a, b = Path(attempt_a).resolve(), Path(attempt_b).resolve()
    pa, pb = json.loads(Path(processing_a).read_text()), json.loads(Path(processing_b).read_text())
    prefix = 'training__C238396__LVMC-11-43-010-A__motor_vehicle_driver__'
    if pa.get('case_id') != prefix + 'probe_a' or pb.get('case_id') != prefix + 'probe_b':
        raise ValueError('Exact comparison cases differ')
    if not all(p.get('passed') is True and p.get('recorded_only') is True for p in (pa, pb)):
        raise ValueError('Recorded-only processing proof missing')
    if sha(a / 'road.xodr') != sha(b / 'road.xodr'):
        raise ValueError('Fixed roundabout geometry differs')
    configs = [json.loads((path / 'config.json').read_text()) for path in (a, b)]
    for field in ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s',
                  'cameras', 'source_actor_ids', 'required_atoms'):
        if configs[0].get(field) != configs[1].get(field):
            raise ValueError('Fixed comparison configuration differs: ' + field)
    if [c['requested_direction'] for c in configs] != ['counterclockwise', 'clockwise']:
        raise ValueError('Declared direction contrast differs')
    controls = [rows(path / 'control-intent.jsonl') for path in (a, b)]
    if any(len(stream) != 600 for stream in controls):
        raise ValueError('Fixed other-traffic schedule lacks 600 frames')
    for left, right in zip(*controls):
        if left['controls']['other'] != right['controls']['other']:
            raise ValueError('Other-vehicle request differs')
    measured = [analyze(path) for path in (a, b)]
    directions = [m['direction']['translational_direction'] for m in measured]
    if directions != ['counterclockwise', 'clockwise']:
        raise ValueError('Measured opposite translational directions absent')
    if diagnostic and any(json.loads((path / 'acquisition-provenance.json').read_text()).get(
            'provenance_kind') != 'synthetic_fixture' for path in (a, b)):
        raise ValueError('Diagnostic comparison requires CPU fixtures')
    return {'format': 'c238396-comparison-audit-v1',
            'case_ids': [m['case_id'] for m in measured],
            'diagnostic_fixture': diagnostic, 'fixed_map_sha256': sha(a / 'road.xodr'),
            'fixed_other_request_frames': 600, 'deliberate_difference': 'direction_sign',
            'measured_directions': directions,
            'signed_radial_cross_sum_m2': [m['direction']['signed_radial_cross_sum_m2']
                                           for m in measured],
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for option in ('attempt-a', 'attempt-b', 'processing-a', 'processing-b', 'output'):
        parser.add_argument('--' + option, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    value = compare(args.attempt_a, args.attempt_b, args.processing_a,
                    args.processing_b, args.diagnostic)
    Path(args.output).write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps(value, sort_keys=True))
