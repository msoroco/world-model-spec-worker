"""Start a source-bound eight-case manifest without fabricated proof receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from author_bundles import CHANNELS
from parking import CASES

ROOT = Path(__file__).resolve().parent
AID = ROOT.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    if (ROOT / 'execution-manifest.json').exists():
        prior = json.loads((ROOT / 'execution-manifest.json').read_text())
        if any(entry.get('compatibility') or entry.get('physical_preparation')
               for entry in prior.get('cases', [])):
            raise ValueError('Do not overwrite a proof-bearing manifest')
    runtime_sha = sha(ROOT.parents[1] / 'runtime/SOURCE-MANIFEST.json')
    entries = []
    for index, item in enumerate(CASES):
        case_id = AID + '__' + item.case_id
        path = 'construction.json' if index == 0 else 'cases/' + item.case_id + '/construction.json'
        entries.append({
            'case_id': case_id, 'kind': 'delivery',
            'construction': path, 'construction_sha256': sha(ROOT / path),
            'fixture_recipe': 'work/' + AID + '/diagnostic-' + item.case_id + '-recipe.json',
            'measurement_contract': 'measurement-contract.json',
            'measurement_procedure': {'entrypoint': 'analysis.py'},
            'source_gate': 'original reviewed highway, curb, route and authority source packet required',
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
                'reason': 'The narrow road may not support stable side-by-side vehicle placement or a complete four-camera view.'},
            'candidates': []})
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': AID, 'status': 'source_gated_draft',
                'runtime_manifest_sha256': runtime_sha, 'cases': entries}
    (ROOT / 'execution-manifest.json').write_text(
        json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
