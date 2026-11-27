"""Create four exact source-gated delivery manifest entries before proof binding."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from author_plan import CHANNELS
from zone_motion import CASES

ROOT = Path(__file__).resolve().parent
AID = ROOT.name


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    path = ROOT / 'execution-manifest.json'
    if path.exists():
        old = json.loads(path.read_text(encoding='utf-8'))
        if any(item.get('compatibility') or item.get('physical_preparation') for item in old.get('cases', [])):
            raise ValueError('Do not overwrite proof-bearing manifest')
    entries = []
    for index, case in enumerate(CASES):
        cid = AID + '__' + case.name
        construction = 'construction.json' if index == 0 else 'cases/' + case.name + '/construction.json'
        entries.append({
            'case_id': cid, 'kind': 'delivery', 'construction': construction,
            'construction_sha256': sha(ROOT / construction),
            'fixture_recipe': 'work/' + AID + '/diagnostic-' + case.name + '-recipe.json',
            'measurement_contract': 'measurement-contract.json',
            'measurement_procedure': {'entrypoint': 'analysis.py'},
            'source_gate': 'reviewed original public highway, official pedestrian-exclusive safety-zone designation, interval, visible marking and source-bound physical boundary required',
            'acquisition': {
                name: {'entrypoint': 'analysis.py',
                       'method': 'original Native frame source and saved-only extraction',
                       'evidence': 'channel-' + name + '.jsonl'} for name in CHANNELS
            },
            'native_handoff': {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT'},
            'candidate_risk': {
                'status': 'physical',
                'reason': 'A narrow designated zone may impede the off-lane transit or complete four-camera view of markers during the full original body motion.',
            },
            'candidates': [],
        })
    path.write_text(json.dumps({
        'format': 'worker-execution-manifest', 'assignment_id': AID,
        'status': 'source_gated_draft',
        'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
        'cases': entries,
    }, indent=2) + '\n', encoding='utf-8')


REPO = ROOT.parents[1]

if __name__ == '__main__':
    main()
