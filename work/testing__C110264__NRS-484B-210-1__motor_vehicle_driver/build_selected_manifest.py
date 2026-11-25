"""Bind exact current-runtime diagnostic constructions and offline proofs.

Later CPU proof builders add their own source-bound receipts. This script never
marks the assignment ready or manufactures compatibility/physical evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    draft = json.loads((HERE / 'execution-manifest.draft.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    channels = {item['name'] for item in plan['cases'][0]['recording_description']['channels']}
    contexts = {item['name'] for item in plan['cases'][0]['recording_description']['context_inputs']}
    entries = []
    for original in draft['cases']:
        case_id = original['case_id']
        suffix = case_id.removeprefix(HERE.name + '__')
        entry = dict(original)
        primary_log = f'cpu-offline-{suffix}-primary.log'
        entry.update(kind='delivery',
                     offline={'command': (f'.venv-cpu/bin/python runtime.py offline --manifest '
                                           f'work/{HERE.name}/execution-manifest.draft.json --case {case_id} '
                                           f'--output .runtime-work/c110264-output/offline6-{suffix}-primary '
                                           '--python $PWD/.venv-cpu/bin/python'),
                              'exit_code': 0, 'log': primary_log,
                              'log_sha256': sha(HERE / primary_log),
                              'construction_sha256': original['construction_sha256']},
                     measurement_contract=f'cases/{suffix}/measurement-contract.json',
                     measurement_procedure={'entrypoint': 'analysis.py'},
                     fixture_recipe=f'work/{HERE.name}/cases/{suffix}/fixture-recipe.json',
                     native_handoff={'python_env_var': 'CARLA_PYTHON',
                                     'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
                     acquisition={name: {'entrypoint': 'pass_right_actor.py',
                                         'method': 'make_actor_sampler',
                                         'evidence': 'original Native actor snapshot and source-bound road'}
                                  for name in channels | contexts})
        for candidate in entry['candidates']:
            log = f'cpu-offline-{suffix}-fallback1.log'
            candidate['offline'] = {
                'command': (f'.venv-cpu/bin/python runtime.py offline --manifest '
                            f'work/{HERE.name}/execution-manifest.draft.json --case {case_id} '
                            f'--candidate fallback1 --output .runtime-work/c110264-output/offline6-{suffix}-fallback1 '
                            '--python $PWD/.venv-cpu/bin/python'),
                'exit_code': 0, 'log': log, 'log_sha256': sha(HERE / log),
                'construction_sha256': candidate['construction_sha256']}
        entries.append(entry)
    output = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
              'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
              'status': 'partial_selected_diagnostic_proofs_pending',
              'cases': entries}
    (HERE / 'execution-manifest.json').write_text(json.dumps(output, indent=2) + '\n')


if __name__ == '__main__':
    main()
