"""Prove the C223016 semantic proposal chain and reject a stale source hash."""
import json
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime' / 'scenario_pipeline'))
from worker_exchange.semantic_delivery import validate


def audit():
    assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    positive = validate(HERE, assignment, manifest)
    with TemporaryDirectory(prefix='c223016-semantic-', dir=ROOT / '.runtime-work') as directory:
        trial = Path(directory)
        shutil.copytree(HERE / 'proposals', trial / 'proposals')
        for case in manifest['cases']:
            source = HERE / case['construction']
            target = trial / case['construction']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        copied = validate(trial, assignment, manifest)
        if copied['selected_cases'] != positive['selected_cases']:
            raise ValueError('Isolated semantic copy changed selected cases')
        template = trial / 'proposals/template.json'
        template.write_bytes(template.read_bytes() + b'\n')
        try:
            validate(trial, assignment, manifest)
        except ValueError as error:
            negative = str(error)
            if negative != 'Stage proposal source hash changed':
                raise
        else:
            raise ValueError('Tampered semantic stage was accepted')
    cases = json.loads((HERE / 'proposals/cases.json').read_text())
    incomplete = [spec['sweep_id'] for spec in cases['sweep_specs']
                  if spec['status'] == 'incomplete']
    return {'format': 'worker-semantic-stage-audit', 'positive': positive,
            'negative_expected_error': negative,
            'numeric_sweep_complete': not incomplete,
            'incomplete_sweep_ids': incomplete,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
