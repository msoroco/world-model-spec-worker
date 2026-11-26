"""Source-bound CPU contrast of two selected electric-bicycle pass plans."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
CASE = HERE.name + '__electric_bicycle_pass_'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def config(mode):
    path = HERE / f'draft-ebike/electric_bicycle_pass_{mode}/primary/construction.json'
    bundle = json.loads(path.read_text())
    embedded = next(item['content'] for item in bundle['files'] if item['path'] == 'config.json')
    return json.loads(embedded), sha(path)


def make(folder, cfg):
    folder.mkdir()
    (folder / 'pass-context.json').write_text(json.dumps({
        'case_id': cfg['case_id'], 'rider_class': 'electric_bicycle',
        'passed_class': 'motor_vehicle', 'rider_dimensions_m': [1.2, .8],
        'motor_dimensions_m': [4, 2], 'motor_occupant_count': 1,
        'source_kind': 'generated_software_diagnostic',
        'rider_qualification': {'wheels': 2, 'operable_pedals': True,
            'saddle': True, 'motor_rated_watts': 500,
            'assist_only_while_pedaling': True, 'assist_cutoff_mph': 20,
            'moped': False, 'electric_scooter': False,
            'source': 'authored generated diagnostic controller'}}) + '\n')
    with (folder / 'participant-poses.jsonl').open('w') as stream:
        for frame in range(600):
            stream.write(json.dumps({'native_frame': frame, 'video_frame': frame,
                'time_s': frame / 20,
                'rider_xy_m': [-50 + frame * .16, cfg['rider_y_m']],
                'motor_xy_m': [-30 + frame * .04, -5.25],
                'drivetrain_command': {'pedaling': True,
                    'pedal_cadence_rpm': 70, 'assist_power_watts': 500,
                    'speed_mps': 3.2, 'assist_cutoff_mps': 20 * .44704,
                    'power_source': 'authored generated diagnostic controller'},
                'synthetic_diagnostic': True}) + '\n')


def main():
    wide, wide_sha = config('wide')
    narrow, narrow_sha = config('narrow')
    assert wide['case_id'] == CASE + 'wide'
    assert narrow['case_id'] == CASE + 'narrow'
    assert wide['rider_y_m'] == -1.75 and narrow['rider_y_m'] == -3.7
    identity = ('case_id', 'selected_case_id', 'supported_case_ids',
                'case_suffix', 'case', 'rider_y_m')
    assert {k: v for k, v in wide.items() if k not in identity} == {
        k: v for k, v in narrow.items() if k not in identity}
    outputs = {}
    root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='c146108-comparison-', dir=root) as temp:
        for mode, cfg in (('wide', wide), ('narrow', narrow)):
            folder = Path(temp) / mode
            make(folder, cfg)
            output = folder / 'measurement.json'
            finished = subprocess.run([sys.executable, str(HERE / 'native/pass_measure.py'),
                '--attempt', str(folder), '--output', str(output)],
                capture_output=True, text=True, timeout=30)
            assert finished.returncode == 0, finished.stderr
            report = json.loads(output.read_text())
            assert report['electric_bicycle_controller_source_checked']
            assert report['endangerment_judgment'] == 'unreviewed'
            outputs[mode] = {'case_id': cfg['case_id'],
                'gap_m': report['minimum_surface_gap_m'],
                'start': report['pass_start_frame'],
                'clear': report['pass_clear_frame'],
                'source_sha256': report['source_sha256']}
    assert outputs['wide']['start'] == outputs['narrow']['start']
    assert outputs['wide']['clear'] == outputs['narrow']['clear']
    assert outputs['wide']['gap_m'] > outputs['narrow']['gap_m'] > 0
    print(json.dumps({'passed': True, 'construction_sha256': {'wide': wide_sha,
        'narrow': narrow_sha}, 'measurements': outputs,
        'controlled_variable': 'rider lateral center and resulting full-body gap',
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False},
        sort_keys=True))


if __name__ == '__main__':
    main()
