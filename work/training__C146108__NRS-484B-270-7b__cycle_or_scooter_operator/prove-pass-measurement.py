"""Generated full-pass source-shape CPU diagnostic, without a safety label."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
MEASURE = HERE / 'native/pass_measure.py'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make(folder, mode):
    folder.mkdir()
    (folder / 'pass-context.json').write_text(json.dumps({
        'rider_class': 'electric_bicycle', 'passed_class': 'motor_vehicle',
        'rider_dimensions_m': [1.2, .8], 'motor_dimensions_m': [4, 2],
        'motor_occupant_count': 2, 'source_kind': 'generated_software_diagnostic',
        'original_native_classification_verified': False,
        'rider_qualification': {'wheels': 2, 'operable_pedals': True,
            'saddle': True, 'motor_rated_watts': 500,
            'assist_only_while_pedaling': True, 'assist_cutoff_mph': 20,
            'moped': False, 'electric_scooter': False,
            'source': 'authored generated diagnostic controller'}}) + '\n')
    with (folder / 'participant-poses.jsonl').open('w') as out:
        for frame in range(600):
            motor_x = frame * .04
            rider_x = -25 + frame * (.08 if mode == 'incomplete' else .16)
            rider_y = 4 if mode == 'wide' else 1.6
            out.write(json.dumps({'native_frame': frame, 'time_s': frame / 20,
                'rider_xy_m': [rider_x, rider_y], 'motor_xy_m': [motor_x, 0],
                'drivetrain_command': {'pedaling': True, 'pedal_cadence_rpm': 70,
                    'assist_power_watts': 500, 'speed_mps': 3.2,
                    'assist_cutoff_mps': 20 * .44704,
                    'power_source': 'authored generated diagnostic controller'},
                'synthetic_diagnostic': True}) + '\n')


def run(folder, output):
    return subprocess.run([sys.executable, str(MEASURE), '--attempt', str(folder),
        '--output', str(output)], capture_output=True, text=True, timeout=30)


def main():
    root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
    root.mkdir(parents=True, exist_ok=True)
    values = []
    with tempfile.TemporaryDirectory(prefix='c146108-pass-', dir=root) as scratch:
        scratch = Path(scratch)
        for mode in ('wide', 'narrow'):
            folder = scratch / mode
            make(folder, mode)
            output = folder / 'measurement.json'
            finished = run(folder, output)
            if finished.returncode:
                raise AssertionError(finished.stderr)
            report = json.loads(output.read_text())
            assert report['first_behind_frame'] == 0
            assert report['pass_start_frame'] < report['pass_clear_frame'] < 600
            assert 9 < report['initial_time_to_rear_overlap_s'] < 10
            assert report['endangerment_judgment'] == 'unreviewed'
            assert not report['legal_verdict_claimed']
            assert report['source_sha256']['participant-poses.jsonl'] == sha(folder / 'participant-poses.jsonl')
            values.append({'mode': mode, 'pass_start_frame': report['pass_start_frame'],
                'pass_clear_frame': report['pass_clear_frame'],
                'minimum_surface_gap_m': report['minimum_surface_gap_m'],
                'initial_time_to_rear_overlap_s': report['initial_time_to_rear_overlap_s'],
                'source_sha256': report['source_sha256']})
        assert values[0]['pass_start_frame'] == values[1]['pass_start_frame']
        assert values[0]['pass_clear_frame'] == values[1]['pass_clear_frame']
        assert values[0]['minimum_surface_gap_m'] > values[1]['minimum_surface_gap_m'] > 0
        missing = scratch / 'missing'
        missing.mkdir()
        (missing / 'pass-context.json').write_text((scratch / 'wide/pass-context.json').read_text())
        failed = run(missing, missing / 'measurement.json')
        assert failed.returncode and 'Missing required source: participant-poses.jsonl' in failed.stderr
        incomplete = scratch / 'incomplete'
        make(incomplete, 'incomplete')
        failed = run(incomplete, incomplete / 'measurement.json')
        assert failed.returncode and 'does not show complete behind-to-clear-ahead pass' in failed.stderr
        broken = scratch / 'bad_join'
        make(broken, 'wide')
        path = broken / 'participant-poses.jsonl'
        lines = path.read_text().splitlines(); row = json.loads(lines[200]); row['native_frame'] = 199
        lines[200] = json.dumps(row); path.write_text('\n'.join(lines) + '\n')
        failed = run(broken, broken / 'measurement.json')
        assert failed.returncode and 'Original Native frame/time join differs' in failed.stderr
        absent = scratch / 'missing_drive'
        make(absent, 'wide')
        lines = (absent / 'participant-poses.jsonl').read_text().splitlines()
        row = json.loads(lines[20]); del row['drivetrain_command']; lines[20] = json.dumps(row)
        (absent / 'participant-poses.jsonl').write_text('\n'.join(lines) + '\n')
        failed = run(absent, absent / 'measurement.json')
        assert failed.returncode and 'original drivetrain command absent' in failed.stderr
        illegal = scratch / 'illegal_assist'
        make(illegal, 'wide')
        lines = (illegal / 'participant-poses.jsonl').read_text().splitlines()
        row = json.loads(lines[20]); row['drivetrain_command']['pedaling'] = False
        lines[20] = json.dumps(row)
        (illegal / 'participant-poses.jsonl').write_text('\n'.join(lines) + '\n')
        failed = run(illegal, illegal / 'measurement.json')
        assert failed.returncode and 'Class 1 assist limit violated' in failed.stderr
    print(json.dumps({'passed': True, 'positive_count': 2, 'negative_count': 5,
        'records': values, 'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
