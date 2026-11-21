"""Attach tested positive/negative CPU delivery contracts to selected laid cases."""
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    if len(manifest['cases']) != 12:
        raise ValueError('Twelve exact selected cases required')
    reference = manifest['cases'][0]
    source = reference['delivery_acceptance']
    script = HERE / 'run_delivery_contract_fixture.py'
    if source['script_sha256'] != sha(script):
        raise ValueError('Existing delivery contract script changed')
    for entry in manifest['cases']:
        short = entry['case_id'].removeprefix(HERE.name + '__')
        if not short.startswith('newly_laid_'):
            continue
        directory = HERE / 'selected-delivery-contracts' / short
        directory.mkdir(parents=True, exist_ok=True)
        contract = copy.deepcopy(source)
        contract['case_id'] = entry['case_id']
        contract['command'] = source['command'].replace(reference['case_id'], entry['case_id'])
        contract['negative_command'] = source['negative_command'].replace(
            reference['case_id'], entry['case_id'])
        for negative in (False, True):
            label = 'negative' if negative else 'positive'
            log = directory / (label + '.log')
            command = [sys.executable, str(script), '--case', entry['case_id']]
            if negative:
                command.append('--negative')
            run = subprocess.run(command, cwd=REPO, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log.write_text(run.stdout)
            if negative:
                if run.returncode == 0 or source['negative_expected_error'] not in run.stdout:
                    raise ValueError('Missing tested negative rejection: ' + short)
                contract['negative_exit_code'] = run.returncode
                contract['negative_log'] = str(log.relative_to(HERE))
                contract['negative_log_sha256'] = sha(log)
            else:
                if run.returncode:
                    raise ValueError('Positive delivery contract failed: ' + short)
                contract['test_exit_code'] = 0
                contract['test_log'] = str(log.relative_to(HERE))
                contract['test_log_sha256'] = sha(log)
        entry['delivery_acceptance'] = contract
        print(json.dumps({'case': short, 'positive': True, 'negative': True,
                          'physical_or_legal_acceptance_claimed': False}))
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'manifest_sha256': sha(MANIFEST), 'selected_cases': 12}))


if __name__ == '__main__':
    main()
