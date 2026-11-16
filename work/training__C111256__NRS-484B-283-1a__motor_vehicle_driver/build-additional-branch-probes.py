"""Test four source-pair branches with 32 distinct primary/fallback CPU plans."""
import hashlib
import json
import subprocess
from pathlib import Path

from additional_branch_probe import CASES, CANDIDATES, BASE, CHANGES, make_rows

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = HERE / 'additional_branch_probe.py'
PYTHON = ROOT / '.venv-cpu/bin/python'
TRIGGERS = {
    'fallback1': {'source': 'Original Native ego body and route centerline',
                  'metric': 'max_route_cross_track_error_m', 'failure_condition': '> 0.45'},
    'fallback2': {'source': 'Original Native ego/pedestrian or guard body clearance',
                  'metric': 'minimum_actor_body_clearance_m', 'failure_condition': '< 0.75 engineering risk probe'},
    'fallback3': {'source': 'Decoded original overview camera actor/body pixels',
                  'metric': 'minimum_actor_pixel_margin_px', 'failure_condition': '< 40'},
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


entries = []
for case, branch in CASES.items():
    source = HERE / 'additional-branch-proofs' / case / 'synthetic-source.json'
    write(source, make_rows(case))
    entry = {'case_id': HERE.name + '__' + case, 'branch': branch,
             'source': str(source.relative_to(HERE)), 'source_sha256': sha(source),
             'candidate_risk': {'status': 'physical',
                                'reason': 'Native geometry, participants, actor eligibility and original pixels remain unverified'},
             'original_native_observed': False, 'legal_verdict': None,
             'candidates': []}
    for candidate in CANDIDATES:
        folder = HERE / 'additional-branch-proofs' / case / candidate
        construction = folder / 'construction.json'
        write(construction, {'format': 'c111256-additional-branch-probe-construction-v1',
                             'case_id': entry['case_id'], 'branch': branch, 'candidate_id': candidate,
                             'cell_id': 'C111256', 'law_id': 'NRS-484B-283-1a',
                             'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'duration_s': 24,
                             'runner': 'additional_branch_probe.py', 'runner_sha256': sha(SCRIPT),
                             'source': str(source.relative_to(HERE)), 'source_sha256': sha(source),
                             'knobs': BASE | CHANGES[candidate],
                             'cameras': ['overview', 'approach', 'reference_corner', 'driver_reference'],
                             'scope': 'source-shaped CPU branch measurement; Native construction and public saved path pending'})
        output, log = folder / 'measurement.json', folder / 'positive.log'
        command = [str(PYTHON), str(SCRIPT), '--case', case, '--candidate', candidate,
                   '--source', str(source), '--output', str(output)]
        with log.open('w') as stream:
            proc = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        if proc.returncode:
            raise ValueError(log.read_text())
        ref = {'id': candidate, 'construction': str(construction.relative_to(HERE)),
               'construction_sha256': sha(construction), 'offline_command': ' '.join(command),
               'offline_exit_code': 0, 'offline_log': str(log.relative_to(HERE)),
               'offline_log_sha256': sha(log), 'measurement': str(output.relative_to(HERE)),
               'measurement_sha256': sha(output)}
        if candidate == 'primary':
            entry['primary'] = ref
        else:
            ref['trigger'] = TRIGGERS[candidate]
            ref['changed_knobs'] = list(CHANGES[candidate])
            entry['candidates'].append(ref)
    negative = HERE / 'additional-branch-proofs' / case / 'missing-source.log'
    with negative.open('w') as stream:
        proc = subprocess.run([str(PYTHON), str(SCRIPT), '--case', case,
                               '--candidate', 'primary', '--source', str(negative.parent / 'absent.json'),
                               '--output', str(negative.parent / 'rejected.json')],
                              cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    if proc.returncode == 0 or 'No such file or directory' not in negative.read_text():
        raise ValueError('Missing branch source was not rejected')
    entry['negative'] = {'exit_code': proc.returncode, 'log': str(negative.relative_to(HERE)),
                         'log_sha256': sha(negative), 'expected': 'No such file or directory'}
    entries.append(entry)
write(HERE / 'additional-branch-proofs' / 'manifest.json', {
    'format': 'c111256-additional-branch-conditional-cpu-probes-v1',
    'assignment_id': HERE.name, 'case_count': len(entries), 'candidate_count': 4 * len(entries),
    'cases': entries, 'scope': 'Synthetic source-shaped geometry/actor probes only; not Native/public selected delivery'})
print(json.dumps({'cases': len(entries), 'candidate_constructions': 4 * len(entries),
                  'positive': 4 * len(entries), 'missing_source_negative': len(entries)}))
