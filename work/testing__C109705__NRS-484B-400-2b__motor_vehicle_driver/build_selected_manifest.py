"""Bind four exact C109705 400(2)(b) cases to current CPU constructions.

This partial manifest records passing offline proofs and leaves unproved
compatibility, saved delivery and audit fields absent until those tests pass.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
NAMES = ('near_centerline', 'farther_from_centerline',
         'imaginary_near_centerline', 'imaginary_farther_from_centerline')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    draft = json.loads((ROOT / 'execution-manifest.draft.json').read_text())
    by_case = {row['case_id']: row for row in draft['cases']}
    cases = []
    for name in NAMES:
        case = ROOT.name + '__' + name
        row = by_case[case]
        source = ROOT / row['construction']
        if sha(source) != row['construction_sha256']:
            raise ValueError('selected construction changed after exact offline proof')
        selected_log = ROOT / f'cpu-selected-offline-{name}.log'
        log_name = selected_log.name if selected_log.is_file() else f'cpu-source-review-review-offline-{name}.log'
        log = ROOT / log_name
        if not log.is_file():
            raise ValueError('current exact offline proof log missing')
        cases.append({
            'case_id': case, 'kind': 'delivery',
            'construction': row['construction'],
            'construction_sha256': row['construction_sha256'],
            'candidate_risk': row['candidate_risk'], 'candidates': [],
            'preparation_status': 'offline_only_partial',
            'offline': {
                'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{ROOT.name}/execution-manifest.json --case {case} --output .runtime-work/c109705-2b-nov24/selected-offline-{name} --python $PWD/.venv-cpu/bin/python',
                'exit_code': 0,
                'construction_sha256': row['construction_sha256'],
                'log': log_name, 'log_sha256': sha(log),
            },
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT'},
        })
    manifest = {
        'format': 'worker-execution-manifest',
        'assignment_id': ROOT.name,
        'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
        'preparation_status': 'offline_only_partial',
        'cases': cases,
    }
    (ROOT / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('bound', len(cases), 'selected partial cases')


if __name__ == '__main__':
    build()
