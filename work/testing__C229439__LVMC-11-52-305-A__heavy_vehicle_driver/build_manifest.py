"""Bind the selected service parking case sources and immutable constructions."""

import hashlib
import json
from pathlib import Path

from service_parking import CASES
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
                                  'requirement': plan['requirement_dispositions'][0]['requirement'],
                                  'source': source,
                                  'output_key': 'service_parking_conditions',
                                  'method': 'measure_service_parking',
                                  'value_type': 'object', 'kind': 'measured',
                                  'inputs': ['original-service-parking.jsonl',
                                             'service-parking-context.json',
                                             'camera-frame-map.jsonl',
                                             'video_frames.jsonl', 'trace.jsonl']}],
                'negative': {'remove': ['original-service-parking.jsonl'],
                             'error_contains': 'Missing required source: original-service-parking.jsonl'}}
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
                     'trigger': {'source': 'original four-camera video and Native worksite/device readback',
                                 'metric': 'worksite task, worker, sign face and complete parked heavy vehicle visible in original frames',
                                 'failure_condition': 'primary worksite or device face is occluded during parked interval'},
                     'changed_knobs': ['reviewed fallback camera placement for same worksite, sign and governed curb']}
        acquisition = {name: {'entrypoint': 'analysis.py',
                              'evidence': 'channel-' + name + '.jsonl',
                              'method': 'source-bound original heavy parking, active work and camera frame joins'}
                       for name in ('commercial_vehicle_dimensions', 'street_adjacency_and_frontage',
                                    'parking_device_permission', 'parked_vehicle_footprint',
                                    'worksite_activity_and_distance', 'loading_and_other_exceptions',
                                    'camera_frame_identity')}
        acquisition.update({name:{'entrypoint':'analysis.py','evidence':name+'.json',
            'method':'reviewed source-hashed original context'} for name in
            ('reviewed_service_parking_sources','reviewed_vehicle_work_identity')})
        entry = {'case_id': cid, 'kind': 'delivery',
                 'construction': str(primary.relative_to(ROOT)),
                 'construction_sha256': sha(primary),
                 'candidate_risk': {'status': 'physical',
                                    'reason': 'Worksite activity or exact sign face can be obscured while the heavy vehicle remains visible.'},
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
