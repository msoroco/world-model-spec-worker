"""Package the selected case dispatcher and four-view measurement plan."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def build():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    source = json.loads((ROOT / 'inputs' / AID / 'assignment.json').read_text())
    cases = [e['case_id'] for e in manifest['cases']]
    cameras = [
        {'name': 'overview', 'width': 1920, 'height': 1080, 'fps': 20,
         'pose_strategy': 'fixed overhead U-turn and adjacent road context', 'fov_deg': 90},
        {'name': 'approach', 'width': 1280, 'height': 720, 'fps': 20,
         'pose_strategy': 'fixed eastbound approach and turning envelope', 'fov_deg': 90},
        {'name': 'reference_corner', 'width': 1280, 'height': 720, 'fps': 20,
         'pose_strategy': 'fixed intersection or divided crossing boundary', 'fov_deg': 85},
        {'name': 'driver_reference', 'width': 1280, 'height': 720, 'fps': 20,
         'pose_strategy': 'fixed departure lane and original vehicle body', 'fov_deg': 90},
    ]
    config = {'assignment_id': AID, 'input_sha256': sha(ROOT / 'inputs' / AID / 'assignment.json'),
              'cell_id': source['cell_id'], 'law_id': source['law_id'], 'actor': source['actor'],
              'supported_case_ids': cases, 'duration_s': 40, 'rate_hz': 20,
              'cameras': cameras, 'required_atoms': [], 'source_packets': [],
              'physical_success_claimed': False,
              'candidate_ids': ['primary', 'fallback1', 'fallback2', 'fallback3']}
    config_path = HERE / 'config.json'
    write(config_path, config)
    recording = json.loads((HERE / manifest['cases'][0]['construction']).read_text())['recording_description']
    for entry in manifest['cases']:
        if json.loads((HERE / entry['construction']).read_text())['recording_description'] != recording:
            raise ValueError('Exact selected cases changed recording channels')
    runner_path = HERE / 'runner.py'
    construction = {'format': 'c111662-selected-root-dispatch-v1',
                    'case_id': cases[0], 'cell_id': source['cell_id'],
                    'law_id': source['law_id'], 'actor': source['actor'],
                    'entrypoint': 'runner.py', 'status': 'selected_cpu_delivery_request',
                    'files': [{'path': 'runner.py', 'source': str(runner_path.relative_to(ROOT)),
                               'content': runner_path.read_text()},
                              {'path': 'config.json', 'source': str(config_path.relative_to(ROOT)),
                               'content': config_path.read_text()}],
                    'measurement_plan': [{'case_id': e['case_id'],
                                          'contract': e['measurement_contract'],
                                          'procedure': e['measurement_procedure']['entrypoint']}
                                         for e in manifest['cases']],
                    'recording_description': recording,
                    'static_checks': ['exact case and candidate identity',
                                      'current input SHA and source-bound offline construction'],
                    'termination_rules': ['retain all original source streams',
                                          'stop after 800 synchronized frames and Native owner release'],
                    'mechanisms': ['runtime-selected case-specific U-turn controller and authored road',
                                   'four named source-camera streams',
                                   'saved original-body and road geometry measurement']}
    write(HERE / 'construction.json', construction)
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'duration_s': 40,
                           'composition': 'synchronized_four_view_primary',
                           'coverage': [
                               {'subject': 'full U-turn path and road approaches', 'interval': 'startup through clearance', 'view': 'overview'},
                               {'subject': 'approach vehicle body and frontage', 'interval': 'approach and turn', 'view': 'approach'},
                               {'subject': 'intersection or median opening boundary', 'interval': 'turn crossing', 'view': 'reference_corner'},
                               {'subject': 'departure body and crossing place', 'interval': 'turn through final observation', 'view': 'driver_reference'}]}
    mapping = plan['source_observation_mapping']
    for term in ('kin.position', 'kin.heading'):
        if term in mapping:
            mapping[term]['channels'] = ['ego_pose']
            mapping[term]['evidence'] = 'Original Native body/heading joined by frame; current CPU fixture is synthetic'
    if 'drv.u_turn' in mapping:
        mapping['drv.u_turn']['channels'] = ['ego_pose', 'u_turn_at_intersection_or_opening']
    write(plan_path, plan)
    print(json.dumps({'case_count': len(cases), 'construction_sha256': sha(HERE / 'construction.json'),
                      'config_sha256': sha(config_path)}))


if __name__ == '__main__':
    build()
