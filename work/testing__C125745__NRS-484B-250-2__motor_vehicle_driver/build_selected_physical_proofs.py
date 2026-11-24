"""Run three exact selected CPU physical outcomes and capture lifecycle checks."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUFFIXES = ('stop_ego_left_near_time', 'stop_opposite_straight',
            'stop_ego_left_near_time_no_device')
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    script = HERE / 'physical_motion_selected_fixture.py'
    env = os.environ.copy()
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c125745-selected-physical')
    for suffix in SUFFIXES:
        case = HERE.name + '__' + suffix
        entry = next(row for row in manifest['cases'] if row['case_id'] == case)
        folder = HERE / 'selected-physical' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        outcomes = []
        lifecycle = None
        for kind in KINDS:
            output = folder / (kind + '.json')
            command = ['.venv-cpu/bin/python', str(script.relative_to(ROOT)),
                       '--case', case, '--kind', kind,
                       '--output', str(output.relative_to(ROOT))]
            completed = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       timeout=90)
            log = folder / (kind + '.log')
            log.write_text(completed.stdout)
            if completed.returncode:
                raise ValueError(case + '/' + kind + ': ' + completed.stdout[-1000:])
            result = json.loads(output.read_text())
            if kind == 'lifecycle':
                if result.get('events') != EVENTS or not result.get('failed_encoder_rejected') or not result.get('premature_release_rejected'):
                    raise ValueError('Lifecycle rejection or closure proof missing')
            elif result.get('physical_checks',{}).get('maneuver',{}).get('status') != {
                    'complete_motion':'met','incomplete_motion':'not_met',
                    'missing_evidence':'unverified'}[kind]:
                raise ValueError('Physical outcome differs: ' + kind)
            row = {'command':' '.join(command), 'exit_code':0, 'kind':kind,
                   'log':str(log.relative_to(HERE)), 'log_sha256':sha(log),
                   'result':str(output.relative_to(HERE)), 'result_sha256':sha(output)}
            if kind == 'lifecycle':
                row['events'] = EVENTS
                lifecycle = row
            else:
                outcomes.append(row)
        receipt = {'format':'worker-c125745-physical-preparation',
                   'case_id':case, 'construction_sha256':entry['construction_sha256'],
                   'diagnostic_fixture_only':True,
                   'fixture_script':script.name, 'fixture_script_sha256':sha(script),
                   'fixtures':outcomes, 'lifecycle':lifecycle,
                   'physical_acceptance_claimed':False}
        receipt_path = folder / 'receipt.json'
        receipt_path.write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n')
        entry['physical_preparation'] = {
            'receipt':str(receipt_path.relative_to(HERE)), 'sha256':sha(receipt_path)}
    manifest_path.write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'cases':list(SUFFIXES),'outcomes_per_case':3,
                      'lifecycle_per_case':1},sort_keys=True))


if __name__ == '__main__':
    main()
