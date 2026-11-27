"""Bind red-curb exact cases to immutable construction and source plans."""

import hashlib
import json
from pathlib import Path

from red_curb import CASES
from source_packet import ASSIGNMENT

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    entries = []
    for index, case in enumerate(CASES):
        cid = ASSIGNMENT + '__' + case.name
        selected = [(i, row) for i, row in enumerate(plan['requirement_dispositions'])
                    if cid in row['case_ids']]
        if len(selected) != 1:
            raise ValueError('each exact case needs one selected red-curb clause')
        disposition_index, disposition = selected[0]
        contract = {
            'format': 'worker-measurement-contract',
            'requirements': [{
                'disposition_index': disposition_index,
                'requirement': disposition['requirement'],
                'source': disposition['source'],
                'output_key': 'red_curb_conditions',
                'method': 'measure_red_curb', 'value_type': 'object',
                'kind': 'measured',
                'inputs': ['original-red-curb-events.jsonl', 'red-curb-context.json',
                           'camera-frame-map.jsonl', 'video_frames.jsonl', 'trace.jsonl']}],
            'negative': {'remove': ['original-red-curb-events.jsonl'],
                         'error_contains': 'Missing required source: original-red-curb-events.jsonl'}}
        contract_path = ROOT / ('measurement-contract.json' if index == 0 else
                                'cases/' + case.name + '/measurement-contract.json')
        contract_path.parent.mkdir(parents=True, exist_ok=True)
        contract_path.write_text(json.dumps(contract, indent=2) + '\n')
        primary = ROOT / ('construction.json' if index == 0
                          else 'cases/' + case.name + '/construction.json')
        fallback = ROOT / 'cases' / case.name / 'fallback1-construction.json'
        entries.append({
            'case_id': cid, 'kind': 'delivery',
            'construction': str(primary.relative_to(ROOT)),
            'construction_sha256': sha(primary),
            'candidate_risk': {
                'status': 'physical',
                'reason': 'Original red paint, sign face or mail-box activity can be hidden by parked vehicle from the primary camera pose.'},
            'candidates': [{
                'id': 'fallback1',
                'construction': str(fallback.relative_to(ROOT)),
                'construction_sha256': sha(fallback),
                'trigger': {
                    'source': 'original four-camera video and Native camera readback',
                    'metric': 'governed red edge and relevant sign or mail box visible with vehicle halt',
                    'failure_condition': 'primary curb or relevant device/activity is occluded during the original halt interval'},
                'changed_knobs': ['reviewed alternate camera placement around the same curb and vehicle']
            }],
            'measurement_contract': str(contract_path.relative_to(ROOT)),
            'fixture_recipe': str((ROOT / 'diagnostics' / case.name /
                                   'fixture-recipe.json').relative_to(REPO)),
            'measurement_procedure': {'entrypoint': 'analysis.py'},
            'acquisition': {name: {'entrypoint': 'analysis.py',
                                   'evidence': 'channel-' + name + '.jsonl',
                                   'method': 'source-bound original red-curb and camera frame joins'}
                            for name in ('red_curb_location', 'sign_and_vehicle_status',
                                         'original_halt_activity', 'exception_purpose',
                                         'attendance_and_engine', 'governing_context',
                                         'camera_frame_identity')},
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT'},
        })
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'cases': entries}
    (ROOT / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    print(len(write()['cases']))
