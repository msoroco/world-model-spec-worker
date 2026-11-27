"""Create proof-free exact manifest entries before CPU proof binding."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from author_bundles import CHANNELS
from fire_station_scene import ASSIGNMENT, CASES


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path = ROOT / 'execution-manifest.json'
    if path.exists():
        prior = json.loads(path.read_text(encoding='utf-8'))
        if any(entry.get('compatibility') or entry.get('physical_preparation')
               for entry in prior.get('cases', [])):
            raise ValueError('refusing to overwrite proof-bearing manifest')
    entries = []
    for index, case in enumerate(CASES):
        construction = ('construction.json' if index == 0 else
                        'cases/' + case.name + '/construction.json')
        entries.append({
            'case_id': case.case_id, 'kind': 'delivery',
            'construction': construction,
            'construction_sha256': sha(ROOT / construction),
            'fixture_recipe': 'work/' + ASSIGNMENT + '/diagnostic-' + case.name + '-recipe.json',
            'measurement_contract': 'measurement-contract.json',
            'measurement_procedure': {'entrypoint': 'analysis.py'},
            'source_gate': 'original reviewed fire-station entrance and public-highway packet required',
            'acquisition': {
                name: {'entrypoint': 'analysis.py',
                       'method': 'original Native frame source and saved-only extraction',
                       'evidence': 'channel-' + name + '.jsonl'}
                for name in CHANNELS},
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT'},
            'candidate_risk': {
                'status': 'physical',
                'reason': 'The opposite-side and entrance-side stop may not achieve a stable terminal halt with body position near the nominated foot boundary.'},
            'candidates': []})
    path.write_text(json.dumps({
        'format': 'worker-execution-manifest',
        'assignment_id': ASSIGNMENT,
        'status': 'source_gated_draft',
        'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
        'cases': entries}, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
