"""Select the source-proved 4 m/s same-traffic case for eventual delivery.

Readiness is still partial: physical-preparation and comparison work remains.
"""

import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SELECTED = HERE / 'execution-manifest.json'
SEPARATE = HERE / 'mid-speed-compatibility-manifest.json'


def main():
    manifest = json.loads(SELECTED.read_text())
    source = json.loads(SEPARATE.read_text())
    if manifest['runtime_manifest_sha256'] != source['runtime_manifest_sha256']:
        raise ValueError('Fifth case uses another pinned runtime')
    entry = copy.deepcopy(source['cases'][0])
    entry['kind'] = 'delivery'
    entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT'}
    ids = [row['case_id'] for row in manifest['cases']]
    if entry['case_id'] in ids:
        current = manifest['cases'][ids.index(entry['case_id'])]
        for key in ('construction', 'construction_sha256', 'fixture_recipe',
                    'measurement_contract'):
            if current.get(key) != entry.get(key):
                raise ValueError('Selected fifth-case source binding changed: ' + key)
        print(json.dumps({'selected_case': entry['case_id'],
                          'already_present': True, 'delivery_ready': False}))
        return
    manifest['cases'].append(entry)
    SELECTED.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'selected_case': entry['case_id'],
                      'manifest_cases': len(manifest['cases']),
                      'delivery_ready': False}))


if __name__ == '__main__':
    main()
