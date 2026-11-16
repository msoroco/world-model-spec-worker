"""Build and test two measured opposite-half cases with three fallback plans each."""
import hashlib
import json
import subprocess
from pathlib import Path

from opposite_half_probe import CASES, CANDIDATES, BASE, CHANGES, make_rows

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = HERE / 'opposite_half_probe.py'
PYTHON = ROOT / '.venv-cpu/bin/python'
TRIGGERS = {
    'fallback1': {'source': 'Original Native ego body and route centerline',
                  'metric': 'max_route_cross_track_error_m', 'failure_condition': '> 0.45'},
    'fallback2': {'source': 'Original Native pedestrian/ego body time series',
                  'metric': 'min_opposite_half_body_clearance_m', 'failure_condition': '< 0.75 engineering risk probe'},
    'fallback3': {'source': 'Decoded original overview camera pixel corners',
                  'metric': 'min_body_pixel_margin_px', 'failure_condition': '< 40'},
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


selected = []
for case in CASES:
    case_id = HERE.name + '__' + case
    source = HERE / 'opposite-half-proofs' / case / 'synthetic-source.json'
    write(source, make_rows(case))
    entry = {'case_id': case_id, 'case': case,
             'source': str(source.relative_to(HERE)), 'source_sha256': sha(source),
             'target_type': 'conditional_cpu_branch_probe',
             'original_native_observed': False, 'legal_danger_judgment': None,
             'candidate_risk': {'status': 'physical', 'reason': 'Opposite-half body clearance, original actor motion and four-camera pixels need Native review'},
             'candidates': []}
    for candidate in CANDIDATES:
        folder = HERE / 'opposite-half-proofs' / case / candidate
        construction = folder / 'construction.json'
        build = {'format': 'c111256-opposite-half-probe-construction-v1',
                 'case_id': case_id, 'candidate_id': candidate,
                 'cell_id': 'C111256', 'law_id': 'NRS-484B-283-1a',
                 'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'duration_s': 24,
                 'runner': 'opposite_half_probe.py', 'runner_sha256': sha(SCRIPT),
                 'source': str(source.relative_to(HERE)), 'source_sha256': sha(source),
                 'knobs': BASE | CHANGES[candidate],
                 'cameras': ['overview', 'approach', 'reference_corner', 'driver_reference'],
                 'measurement': ['minimum_body_clearance_m', 'minimum_clearance_time_s',
                                 'pedestrian_remained_opposite_half'],
                 'legal_danger_threshold': None, 'legal_danger_judgment': None,
                 'construction_scope': 'source-shaped CPU geometry only; Native capture not implemented'}
        write(construction, build)
        result = folder / 'measurement.json'
        log = folder / 'positive.log'
        command = [str(PYTHON), str(SCRIPT), '--case', case, '--candidate', candidate,
                   '--source', str(source), '--output', str(result)]
        with log.open('w') as stream:
            completed = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        if completed.returncode:
            raise ValueError(log.read_text())
        ref = {'id': candidate, 'construction': str(construction.relative_to(HERE)),
               'construction_sha256': sha(construction), 'offline_command': ' '.join(command),
               'offline_exit_code': 0, 'offline_log': str(log.relative_to(HERE)),
               'offline_log_sha256': sha(log), 'measurement': str(result.relative_to(HERE)),
               'measurement_sha256': sha(result)}
        if candidate == 'primary':
            entry['primary'] = ref
        else:
            ref['trigger'] = TRIGGERS[candidate]
            ref['changed_knobs'] = list(CHANGES[candidate])
            entry['candidates'].append(ref)
    negative = HERE / 'opposite-half-proofs' / case / 'missing-source.log'
    with negative.open('w') as stream:
        proc = subprocess.run([str(PYTHON), str(SCRIPT), '--case', case, '--candidate', 'primary',
                               '--source', str(negative.parent / 'absent.json'),
                               '--output', str(negative.parent / 'rejected.json')],
                              cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    if proc.returncode == 0 or 'No such file or directory' not in negative.read_text():
        raise ValueError('Missing source was not rejected')
    entry['negative'] = {'exit_code': proc.returncode, 'log': str(negative.relative_to(HERE)),
                         'log_sha256': sha(negative), 'expected': 'No such file or directory'}
    selected.append(entry)
manifest = {'format': 'c111256-opposite-half-conditional-cpu-probe-v1',
            'assignment_id': HERE.name, 'case_count': 2, 'candidate_count': 8,
            'cases': selected,
            'comparison': {'case_ids': [x['case_id'] for x in selected],
                           'fixed_conditions': ['same two-directional marked-crosswalk geometry',
                                                'same ego trajectory and camera contract',
                                                'pedestrian remains on opposite directional half'],
                           'deliberate_difference': 'measured opposite-half pedestrian body proximity',
                           'legal_judgment': None},
            'scope': 'CPU source-shaped branch probe only; excludes Native/public compatibility and delivery selection'}
write(HERE / 'opposite-half-proofs' / 'manifest.json', manifest)
print(json.dumps({'cases': 2, 'candidate_constructions': 8, 'positive': 8,
                  'missing_source_negative': 2, 'legal_judgment': None}))
