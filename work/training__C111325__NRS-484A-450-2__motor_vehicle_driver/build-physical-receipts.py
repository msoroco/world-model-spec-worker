"""Bind three source-derived physical fixture outcomes and closure ordering."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    receipts = []
    for index in (1, 2):
        folder = HERE / 'physical-preparation' / str(index)
        construction = HERE / f'selected-probe-{index}-primary-construction.json'
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            result = folder / f'{kind}-result.json'
            log = folder / f'{kind}.log'
            fixtures.append({
                'kind': kind,
                'command': f'SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c111325-selected/physical-output PYTHONPATH=$PWD/runtime/scenario_pipeline PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{HERE.name}/prove-selected-physical.py --probe {index} --kind {kind}',
                'exit_code': 0, 'log': log.relative_to(HERE).as_posix(),
                'log_sha256': sha(log),
                'result': result.relative_to(HERE).as_posix(),
                'result_sha256': sha(result),
            })
        lifecycle = folder / 'lifecycle.log'
        receipt = {'format': 'c111325-physical-preparation-v1',
                   'case_id': HERE.name + f'__probe_{index}',
                   'construction_sha256': sha(construction),
                   'fixtures': fixtures,
                   'lifecycle': {
                       'events': ['capture_finished', 'encoders_closed',
                                  'restoration_verified', 'native_exit',
                                  'owner_released', 'saved_processing_started'],
                       'exit_code': 0,
                       'command': f'SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c111325-selected/physical-output PYTHONPATH=$PWD/runtime/scenario_pipeline PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{HERE.name}/prove-selected-physical.py --probe {index} --kind lifecycle',
                       'log': lifecycle.relative_to(HERE).as_posix(),
                       'log_sha256': sha(lifecycle),
                   },
                   'physical_acceptance_claimed': False}
        path = folder / 'receipt.json'
        path.write_text(json.dumps(receipt, indent=2) + '\n')
        receipts.append({'case': index, 'sha256': sha(path)})
    return receipts


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
