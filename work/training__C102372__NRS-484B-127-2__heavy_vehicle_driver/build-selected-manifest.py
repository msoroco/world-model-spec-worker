"""Bind retained exact constructions to the active runtime for selected proof work."""
from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main() -> None:
    draft = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    runtime = json.loads((ROOT / 'batch.json').read_text())['runtime']['source_manifest_sha256']
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
                'runtime_manifest_sha256': runtime,
                'status': 'selected_cpu_proofs_in_progress', 'cases': []}
    for old in draft['cases']:
        entry = dict(old)
        entry['kind'] = 'delivery'
        if entry['case_id'].endswith('__probe_1'):
            entry['fixture_recipe'] = (HERE / 'selected-fixture/probe_1/recipe.json').relative_to(ROOT).as_posix()
            entry['measurement_contract'] = 'selected-fixture/probe_1/measurement-contract.json'
            entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                       'host_env_var': 'CARLA_HOST',
                                       'port_env_var': 'CARLA_PORT'}
        manifest['cases'].append(entry)
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'selected_cases': len(manifest['cases']),
                      'runtime_manifest_sha256': runtime}, sort_keys=True))


if __name__ == '__main__':
    main()
