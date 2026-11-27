"""Bind exact selected cases to their source-hashed CPU proof slots."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from author_semantics import CHANNEL_NAMES, SOURCE


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n',
                    encoding='utf8')


def main():
    batch = json.loads((REPO / 'batch.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    entries = []
    for index, case in enumerate(plan['cases']):
        cid = case['case_id']
        suffix = cid.removeprefix(AID + '__')
        base = 'cases/' + suffix + '/'
        construction = 'construction.json' if index == 0 else base + 'construction.json'
        fallback = base + 'fallback1/construction.json'
        selected = [
            (i, item) for i, item in enumerate(plan['requirement_dispositions'])
            if cid in item['case_ids']
        ]
        contract = {
            'format': 'worker-measurement-contract',
            'assignment_id': AID, 'case_id': cid,
            'requirements': [{
                'disposition_index': i,
                'requirement': item['requirement'],
                'source': item['source'],
                'output_key': item['output_key'],
                'method': 'analyze', 'value_type': 'object',
                'kind': 'measured' if item['output_key'] in (
                    'same_lane_passage','same_lane_two_wheeler_count')
                    else 'sourced_context',
                'inputs': ['same-lane-history.jsonl', 'same-lane-scene.json',
                           'trace.jsonl', 'video_frames.jsonl'],
            } for i, item in selected],
            'negative': {'remove': ['same-lane-scene.json'],
                         'error_contains': 'Missing required source: same-lane-scene.json'},
            'scope': 'Synthetic compatibility of source-bound original-frame measurements, without physical or legal finding',
        }
        contract_path = base + 'measurement-contract.json'
        write(ROOT / contract_path, contract)
        entry = {
            'case_id': cid, 'kind': 'delivery',
            'construction': construction,
            'construction_sha256': sha(ROOT / construction),
            'candidate_risk': {
                'status': 'physical',
                'reason': 'Same-lane motorcycle side-by-side spawn and relative motion may fail Native collision avoidance or upstream camera framing; original actor readback and pixels decide.',
            },
            'candidates': [{
                'id': 'fallback1', 'construction': fallback,
                'construction_sha256': sha(ROOT / fallback),
                'trigger': {
                    'source': 'original Native actor trajectory and synchronized four-view pixel review',
                    'metric': 'spawn clearance, relative pass/abreast motion and full participant visibility',
                    'failure_condition': 'primary spawn is blocked or required bodies/lane footprint leave the original camera views',
                },
                'changed_knobs': ['all participants start 3 m earlier along the same surveyed route'],
                'offline': {}, 'compatibility': {},
            }],
            'measurement_contract': contract_path,
            'measurement_procedure': {'entrypoint': 'analysis.py'},
            'fixture_recipe': str((ROOT / ('diagnostic-' + suffix + '-recipe.json')).relative_to(REPO)),
            'offline': {}, 'compatibility': {}, 'negative': {},
            'physical_preparation': {},
            'post_capture': {}, 'delivery_acceptance': {},
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT'},
            'acquisition': {
                name: {'entrypoint': 'analysis.py',
                       'method': 'original Native participant, scene and frame-map source join',
                       'evidence': 'channel-' + name + '.jsonl'}
                for name in CHANNEL_NAMES
            },
        }
        entries.append(entry)
    manifest = {
        'format': 'worker-execution-manifest', 'assignment_id': AID,
        'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
        'cases': entries,
    }
    write(ROOT / 'execution-manifest.json', manifest)


if __name__ == '__main__':
    main()
