"""Bind the selected City-space case sources and immutable constructions."""

import hashlib
import json
from pathlib import Path

from city_space import CASES
from source_packet import ASSIGNMENT

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    source = plan['requirement_dispositions'][0]['source']
    contract = {'format': 'worker-measurement-contract',
                'requirements': [{'disposition_index': 0,
                                  'requirement': 'LVMC-11-52-340',
                                  'source': source,
                                  'output_key': 'city_space_conditions',
                                  'method': 'measure_city_space',
                                  'value_type': 'object', 'kind': 'measured',
                                  'inputs': ['original-city-space.jsonl',
                                             'city-space-context.json',
                                             'camera-frame-map.jsonl',
                                             'video_frames.jsonl', 'trace.jsonl']}],
                'negative': {'remove': ['original-city-space.jsonl'],
                             'error_contains': 'Missing required source: original-city-space.jsonl'}}
    (ROOT / 'measurement-contract.json').write_text(json.dumps(contract, indent=2) + '\n')
    entries = []
    for index, case in enumerate(CASES):
        cid = ASSIGNMENT + '__' + case.name
        primary = ROOT / ('construction.json' if index == 0
                          else 'cases/' + case.name + '/construction.json')
        fallback = ROOT / 'cases' / case.name / 'fallback1-construction.json'
        candidate = {'id': 'fallback1',
                     'construction': str(fallback.relative_to(ROOT)),
                     'construction_sha256': sha(fallback),
                     'trigger': {'source': 'original four-camera video and Native device readback',
                                 'metric': 'official device face and complete parked footprint visible in original frames',
                                 'failure_condition': 'primary device face is occluded during parked interval'},
                     'changed_knobs': ['reviewed fallback camera placement for same device and governed space']}
        acquisition = {name: {'entrypoint': 'analysis.py',
                              'evidence': 'channel-' + name + '.jsonl',
                              'method': 'source-bound original parking and camera frame joins'}
                       for name in ('vehicle_status', 'space_authority',
                                    'space_occupancy', 'parking_motion',
                                    'camera_frame_identity')}
        entry = {'case_id': cid, 'kind': 'delivery',
                 'construction': str(primary.relative_to(ROOT)),
                 'construction_sha256': sha(primary),
                 'candidate_risk': {'status': 'physical',
                                    'reason': 'Official device face can be obscured from primary camera while the parked vehicle remains visible.'},
                 'candidates': [candidate],
                 'measurement_contract': 'measurement-contract.json',
                 'fixture_recipe': str((ROOT / 'diagnostics' / case.name /
                                        'fixture-recipe.json').relative_to(REPO)),
                 'measurement_procedure': {'entrypoint': 'analysis.py'},
                 'acquisition': acquisition,
                 'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                    'host_env_var': 'CARLA_HOST',
                                    'port_env_var': 'CARLA_PORT'}}
        entries.append(entry)
    runtime_hash = sha(REPO / 'runtime/SOURCE-MANIFEST.json')
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': runtime_hash,
                'cases': entries}
    (ROOT / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    print(len(write()['cases']))
