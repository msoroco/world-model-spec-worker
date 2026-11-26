"""Initialize exact rear-signal manifest; later bind current-hash proofs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rear_signal import CASES

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
CHANNELS = ('scene_source', 'one_way_route', 'ego_motion', 'rear_motion',
            'rear_driver', 'rear_relation', 'signal_display',
            'rear_signal_visibility', 'maneuver_event', 'camera_frame_map')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    disposition = plan['requirement_dispositions'][0]
    contract = {'format': 'worker-measurement-contract',
                'requirements': [{'disposition_index': 0,
                                  'requirement': disposition['requirement'],
                                  'source': disposition['source'],
                                  'output_key': 'rear_signal_order_and_recipient',
                                  'method': 'analyze', 'value_type': 'object',
                                  'kind': 'measured',
                                  'inputs': ['rear-signal-history.jsonl', 'rear-signal-scene.json',
                                             'video_frames.jsonl', 'trace.jsonl']}],
                'negative': {'remove': ['rear-signal-scene.json'],
                             'error_contains': 'Missing required source: rear-signal-scene.json'}}
    write(ROOT / 'measurement-contract.json', contract)
    entries = []
    for i, item in enumerate(CASES):
        cid = AID + '__' + item.case_id
        construction = ROOT / ('construction.json' if i == 0 else
                                'cases/' + item.case_id + '/construction.json')
        entries.append({'case_id': cid, 'kind': 'delivery',
                        'construction': str(construction.relative_to(ROOT)),
                        'construction_sha256': sha(construction),
                        'fixture_recipe': str((ROOT / ('diagnostic-' + item.case_id + '-recipe.json')).relative_to(REPO)),
                        'measurement_contract': 'measurement-contract.json',
                        'measurement_procedure': {'entrypoint': 'analysis.py'},
                        'source_gate': 'reviewed original one-way scene, rear driver, signal display and visibility absent',
                        'acquisition': {name: {'entrypoint': 'analysis.py',
                                               'method': 'original Native two-participant signal and motion readback',
                                               'evidence': 'channel-' + name + '.jsonl'}
                                        for name in CHANNELS},
                        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                           'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
                        'candidate_risk': {'status': 'none',
                                           'reason': 'Reviewed rear-driver route and signal device are source gated; no distinct CPU-grounded fallback trigger is established.'},
                        'candidates': []})
    write(ROOT / 'execution-manifest.json', {'format': 'worker-execution-manifest',
                                              'assignment_id': AID,
                                              'status': 'source_gated_draft',
                                              'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                                              'cases': entries})


if __name__ == '__main__':
    main()
