"""Exercise source joins and statutory boundaries with explicitly synthetic rows."""
import copy
import hashlib
import json
from pathlib import Path

from measure_lighting import measure


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SCRATCH = ROOT / '.runtime-work' / 'c230241-lighting-proof'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_case(name, rows, context):
    directory = SCRATCH / name
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / 'source.jsonl'
    setup = directory / 'context.json'
    source.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    setup.write_text(json.dumps(context, sort_keys=True, indent=2) + '\n')
    return source, setup


def run_case(name, rows, context, expected, error=None):
    source, setup = write_case(name, rows, context)
    try:
        result = measure(source, setup)
        if error:
            raise AssertionError(name + ' unexpectedly passed')
        for key, value in expected.items():
            assert result['measurements'][key] == value, (name, key, result['measurements'][key])
        assert result['frames'] == 600 and result['duration_s'] == 30
        assert result['original_native_verified'] is False
        assert result['physical_visibility_verified'] is False
        assert result['legal_verdict_claimed'] is False
        return {'case': name, 'passed': True, 'source_sha256': digest(source),
                'context_sha256': digest(setup), 'observed': expected}
    except ValueError as exc:
        if error is None or error not in str(exc):
            raise
        return {'case': name, 'passed': True, 'source_sha256': digest(source),
                'context_sha256': digest(setup), 'expected_rejection': str(exc)}


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    context = {'source_kind': 'synthetic_native_sample',
               'vehicle_class_source': 'diagnostic fixture class',
               'clock_source': 'diagnostic fixture clock',
               'range_calibration_source': 'diagnostic fixture distance',
               'visibility_review_source': 'diagnostic fixture weather',
               'vehicle_covered': True, 'headlamp_count': 1,
               'tail_lamp_rear_mounted': True,
               'sunset_utc_s': 10000, 'next_sunrise_utc_s': 50000}
    rows = [{'native_frame': index, 'time_s': index / 20,
             'utc_s': 11801 + index / 20, 'speed_mps': 3.0,
             'headlamp_lit': True, 'tail_lamp_lit': True,
             'headlamp_white': True, 'tail_lamp_red': True,
             'front_visible_ft': 300, 'rear_visible_ft': 500,
             'discernible_500ft': True} for index in range(600)]
    checks = []
    checks.append(run_case('night-boundary-equal', rows, context,
                           {'required_burning_frames': 600,
                            'headlamp_dark_frames': 0,
                            'front_below_300ft_frames': 0,
                            'rear_below_500ft_frames': 0}))
    for name, field, value, metric in (
            ('headlamp-dark', 'headlamp_lit', False, 'headlamp_dark_frames'),
            ('tail-dark', 'tail_lamp_lit', False, 'tail_lamp_dark_frames'),
            ('front-299', 'front_visible_ft', 299, 'front_below_300ft_frames'),
            ('rear-499', 'rear_visible_ft', 499, 'rear_below_500ft_frames'),
            ('headlamp-nonwhite', 'headlamp_white', False, 'headlamp_nonwhite_frames'),
            ('tail-nonred', 'tail_lamp_red', False, 'tail_lamp_nonred_frames')):
        changed = copy.deepcopy(rows)
        changed[-1][field] = value
        checks.append(run_case(name, changed, context, {metric: 1}))
    day = copy.deepcopy(rows)
    for row in day:
        row['utc_s'] = 9000 + row['time_s']
        row['headlamp_lit'] = False
        row['tail_lamp_lit'] = False
    checks.append(run_case('day-clear', day, context,
                           {'required_burning_frames': 0,
                            'headlamp_dark_frames': 0,
                            'tail_lamp_dark_frames': 0}))
    low = copy.deepcopy(day)
    for row in low:
        row['discernible_500ft'] = False
    checks.append(run_case('day-low-visibility', low, context,
                           {'required_burning_frames': 600,
                            'headlamp_dark_frames': 600,
                            'tail_lamp_dark_frames': 600}))
    corrupt = copy.deepcopy(rows)
    corrupt[-1]['native_frame'] = 598
    checks.append(run_case('bad-frame-join', corrupt, context, {},
                           'Original lighting frame join differs at 599'))
    no_provenance = dict(context)
    no_provenance.pop('clock_source')
    checks.append(run_case('missing-provenance', rows, no_provenance, {},
                           'Source provenance incomplete'))
    no_rear = dict(context)
    no_rear['tail_lamp_rear_mounted'] = False
    checks.append(run_case('missing-rear-mount', rows, no_rear, {},
                           'Lamp equipment placement or count unresolved'))
    receipt = {'format': 'c230241-lighting-measurement-proof-v1',
               'script_sha256': digest(Path(__file__)),
               'measurement_sha256': digest(HERE / 'measure_lighting.py'),
               'diagnostic_only': True, 'checks': checks}
    output = HERE / 'lighting-measurement-proof.json'
    output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'checks_passed': len(checks), 'receipt': str(output),
                      'receipt_sha256': digest(output)}))


if __name__ == '__main__':
    main()
