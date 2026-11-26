"""Saved-source finalizer proof with explicit diagnostic fixtures."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
CASES = ('bicycle_pass_wide', 'electric_bicycle_pass_wide',
         'electric_bicycle_pass_narrow')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv', 'raw.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def construction(suffix):
    family = 'draft-bicycle' if suffix.startswith('bicycle') else 'draft-ebike'
    return json.loads((HERE / family / suffix / 'primary/construction.json').read_text())


def make(folder, suffix):
    folder.mkdir()
    bundle = construction(suffix)
    config = json.loads(next(f['content'] for f in bundle['files'] if f['path'] == 'config.json'))
    (folder / 'construction.json').write_text(json.dumps(bundle, indent=2) + '\n')
    (folder / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    for video in VIDEOS:
        (folder / video).write_bytes(b'generated diagnostic marker; not Native footage\n')
    context = {'case_id': config['case_id'], 'rider_class': config['rider_class'],
        'passed_class': 'motor_vehicle', 'rider_dimensions_m': [1.2, .8],
        'motor_dimensions_m': [4, 2], 'motor_occupant_count': 1,
        'source_kind': 'generated_software_diagnostic'}
    if config['rider_class'] == 'electric_bicycle':
        context['rider_qualification'] = {'wheels': 2, 'operable_pedals': True,
            'saddle': True, 'motor_rated_watts': 500,
            'assist_only_while_pedaling': True, 'assist_cutoff_mph': 20,
            'moped': False, 'electric_scooter': False,
            'source': 'authored generated diagnostic controller'}
    (folder / 'pass-context.json').write_text(json.dumps(context) + '\n')
    (folder / 'capture').mkdir()
    with ((folder / 'participant-poses.jsonl').open('w') as pose,
          (folder / 'trace.jsonl').open('w') as trace,
          (folder / 'video_frames.jsonl').open('w') as mapping,
          (folder / 'capture/evidence.jsonl').open('w') as evidence):
        for frame in range(600):
            t = frame / 20
            rider = [-50 + .16 * frame, config.get('rider_y_m', -1.75)]
            motor = [-30 + .04 * frame, -5.25]
            data = {'native_frame': frame, 'video_frame': frame, 'time_s': t,
                    'rider_xy_m': rider, 'motor_xy_m': motor,
                    'rider_actor_id': 101, 'motor_actor_id': 202}
            if config['rider_class'] == 'electric_bicycle':
                data['drivetrain_command'] = {'pedaling': True,
                    'pedal_cadence_rpm': 70, 'assist_power_watts': 500,
                    'speed_mps': 3.2, 'assist_cutoff_mps': 20 * .44704,
                    'power_source': 'authored generated diagnostic controller'}
            pose.write(json.dumps(data) + '\n')
            trace.write(json.dumps({'frame': frame, 'time_s': t,
                'position_m': [*rider, 1], 'heading_deg': 0, 'speed_mps': 3.2}) + '\n')
            mapping.write(json.dumps({'video_frame': frame, 'carla_frame': frame,
                'native_frame': frame, 'time_s': t,
                'camera_native_frames': {name[:-4]: frame for name in VIDEOS[:-1]}}) + '\n')
            evidence.write(json.dumps({'original_frame': frame,
                'recording_time_s': t, 'actor_id': 101}) + '\n')
    return config


def run(folder):
    result = subprocess.run([sys.executable, str(HERE / 'native/finalize.py'),
        '--attempt', str(folder), '--output', str(folder / 'analysis-report.json')],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, 'PYTHONPATH': str(HERE.parents[1] / 'runtime/scenario_pipeline')})
    return result


def main():
    sys.path.insert(0, str(HERE.parents[1] / 'runtime/scenario_pipeline'))
    from worker_exchange.measurement_contract import verify_report
    root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
    root.mkdir(parents=True, exist_ok=True)
    outputs = {}
    with tempfile.TemporaryDirectory(prefix='c146108-finalize-', dir=root) as temp:
        temp = Path(temp)
        for suffix in CASES:
            folder = temp / suffix
            config = make(folder, suffix)
            result = run(folder)
            assert result.returncode == 0, result.stderr
            report = json.loads((folder / 'analysis-report.json').read_text())
            contract = json.loads((HERE / f'{suffix}-measurement-contract.json').read_text())
            verified = verify_report(contract, report, folder)
            assert set(verified) == {'full_pass'}
            outcome = json.loads((folder / 'result.json').read_text())
            assert report['case_id'] == config['case_id']
            assert report['measurements']['full_pass']['value']['pass_clear_frame'] < 600
            assert not report['physical_or_legal_acceptance']
            assert not outcome['accepted'] and not outcome['setup_confirmed']
            assert len(list((folder / 'channels').glob('*.jsonl'))) == 9
            assert (folder / 'channels/motor_occupants.json').is_file()
            outputs[suffix] = {'analysis_sha256': sha(folder / 'analysis-report.json'),
                               'result_sha256': sha(folder / 'result.json'),
                               'channel_count': 9, 'context_count': 1}
        missing = temp / 'missing'
        make(missing, 'electric_bicycle_pass_wide')
        (missing / 'pass-context.json').unlink()
        failed = run(missing)
        assert failed.returncode and 'Missing required source: pass-context.json' in failed.stderr
        broken = temp / 'broken'
        make(broken, 'electric_bicycle_pass_wide')
        path = broken / 'video_frames.jsonl'
        lines = path.read_text().splitlines()
        row = json.loads(lines[15]); row['carla_frame'] = 14
        lines[15] = json.dumps(row); path.write_text('\n'.join(lines) + '\n')
        failed = run(broken)
        assert failed.returncode and 'Original rider/frame/capture join differs' in failed.stderr
    print(json.dumps({'passed': True, 'positive_cases': outputs,
        'negative_count': 2, 'fixture_kind': 'generated_software_diagnostic',
        'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
