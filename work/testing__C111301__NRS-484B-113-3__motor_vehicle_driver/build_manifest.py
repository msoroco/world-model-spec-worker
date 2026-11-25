"""Draft selected manifest; proof fields are added only after actual checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    aid = HERE.name
    cases = []
    for suffix in ('pedestrian_yield', 'pedestrian_continue'):
        case_id = aid + '__' + suffix
        construction = ('construction.json' if suffix == 'pedestrian_yield'
                        else 'construction-' + suffix + '.json')
        cases.append({
            'case_id': case_id, 'kind': 'delivery',
            'construction': construction,
            'construction_sha256': sha(HERE / construction),
            'measurement_contract': 'measurement-' + suffix + '.json',
            'measurement_procedure': {'entrypoint': 'analysis.py'},
            'candidate_risk': {
                'status': 'none',
                'reason': 'No site-specific failure mechanism justifies an alternate before original site review.'},
            'candidates': [],
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT'}})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': aid,
                'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'cases': cases}
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return [entry['case_id'] for entry in cases]


if __name__ == '__main__':
    print(json.dumps(build()))
