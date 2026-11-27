"""Expose first selected construction and exact source observation plan at root."""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NATIVE = ROOT / 'native'


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    primary = json.loads((NATIVE / 'selected-witness_1-construction.json').read_text())
    config = json.loads(next(item['content'] for item in primary['files'] if item['path'] == 'config.json'))
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    config['supported_case_ids'] = [item['case_id'] for item in plan['cases']]
    for camera in config['cameras']:
        camera['pose_strategy'] = 'vehicle_attached_fixed_source_view'
    shutil.copyfile(NATIVE / 'selected_runner.py', ROOT / 'runner.py')
    write(ROOT / 'config.json', config)
    (ROOT / 'tests').mkdir(exist_ok=True)
    shutil.copyfile(NATIVE / 'selected_offline_test.py', ROOT / 'tests/test_offline.py')
    construction = json.loads(json.dumps(primary))
    construction['files'] = []
    for name, path in (('runner.py', ROOT / 'runner.py'), ('config.json', ROOT / 'config.json'),
                       ('tests/test_offline.py', ROOT / 'tests/test_offline.py'),
                       ('finalize.py', NATIVE / 'finalize.py'),
                       ('saved_hydrant.py', NATIVE / 'saved_hydrant.py')):
        item = {'path': name, 'content': path.read_text()}
        if path.parent == NATIVE:
            item['source'] = 'work/' + ROOT.name + '/native/' + path.name
        construction['files'].append(item)
    construction['measurement_plan'] = {'channels': [item['name'] for item in
                                             primary['recording_description']['channels']],
                                    'source': 'original Native actor, hydrant survey and four camera frame joins'}
    construction['static_checks'] = ['exact law and cell identity', 'four original source cameras',
                                     '20 Hz for 30 seconds', 'source permission and hydrant survey']
    construction['termination_rules'] = ['600 original simulation frames', 'encoder closure',
                                         'world restoration and Native exit before saved analysis']
    construction['mechanisms'] = ['surveyed hydrant and parking permission',
                                  'source-measured vehicle body clearance',
                                  'saved source-bound finalizer']
    write(ROOT / 'construction.json', construction)
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'duration_s': 30,
                           'composition': 'synchronized_four_view_primary',
                           'coverage': [{'subject': subject, 'interval': 'all 30 seconds / 600 frames',
                                         'view': view} for view, subject in (
                                             ('overview', 'vehicle and surveyed hydrant'),
                                             ('approach', 'vehicle approach to hydrant area'),
                                             ('reference_corner', 'hydrant, vehicle body and curb'),
                                             ('driver_reference', 'driver view and regulatory context'))]}
    refs = ['native/selected-witness_1-fixture-recipe.json',
            'native/selected-witness_2-fixture-recipe.json', 'native/saved_hydrant.py']
    plan['source_observation_mapping'] = {
        item['name']: {'evidence': 'Original source-joined 600-frame saved diagnostic and four-camera review; no legal verdict',
                       'channels': [item['name']], 'source_refs': refs}
        for item in plan['observations']}
    for item in plan['observations']:
        item['status'] = 'cpu_source_bound_original_native_pending'
    for item in plan['cases']:
        item['planning_status'] = 'cpu_prepared_original_native_pending'
    for item in plan['comparisons']:
        item['status'] = 'cpu_prepared_original_native_pending'
        item['audit_gap'] = 'Original Native parking motion, pixels, physical clearance and legal review remain pending.'
    write(plan_path, plan)
    print(json.dumps({'root_case': primary['case_id'], 'selected_cases': len(plan['cases'])}))


if __name__ == '__main__':
    main()
