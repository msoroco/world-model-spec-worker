"""Materialize canonical first-case executor and complete four-view plan."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    mapping = plan['source_observation_mapping']
    if isinstance(mapping, list):
        normalized = {}
        for item in mapping:
            term = item['term']
            value = {key: val for key, val in item.items() if key != 'term'}
            value['channels'] = ['exposure_gap_m'] if term == 'rel.surface_gap' else []
            normalized[term] = value
        plan['source_observation_mapping'] = normalized
    plan['observations'] = [{
        'name': 'exposure_gap_m', 'unit': 'm', 'mandatory': True,
        'method': 'Original 20 Hz subject and exposed-body polygons; original velocity, contact and time-to-conflict observations remain separately retained in exposed_actor_footprints.jsonl.'}]
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 8,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'complete subject and exposed body, narrow roadway and verge',
             'interval': 'entire eight-second original-frame exposure'},
            {'view': 'approach', 'subject': 'subject approach, exposed person or property and potential contact',
             'interval': 'entire eight-second original-frame exposure'},
            {'view': 'reference_corner', 'subject': 'both body edges and outside lane edge',
             'interval': 'entire eight-second original-frame exposure'},
            {'view': 'driver_reference', 'subject': 'forward route and exposed body presentation',
             'interval': 'entire eight-second original-frame exposure'}]}
    plan['review_status'] = ('CPU prepared nine exact cases and source-bound comparisons; '
                             'Native speed, clearance, visibility and legal endangerment remain unreviewed.')
    write(plan_path, plan)

    primary = json.loads((HERE / 'cases/construction-slow_person_exposure.json').read_text())
    config = json.loads(next(item['content'] for item in primary['files']
                             if item['path'] == 'config.json'))
    config['supported_case_ids'] = [item['case_id'] for item in plan['cases']]
    config['cameras'] = [
        {'name': name, 'width': width, 'height': height,
         'pose_strategy': 'subject-mounted provisional complete-body source view',
         'fov_deg': fov}
        for name, width, height, fov in (
            ('overview', 1920, 1080, 95), ('approach', 1280, 720, 90),
            ('reference_corner', 1280, 720, 100),
            ('driver_reference', 1280, 720, 85))]
    write(HERE / 'config.json', config)
    (HERE / 'runner.py').write_text((HERE / 'native_exposure_cases.py').read_text())
    construction = dict(primary)
    construction['entrypoint'] = 'runner.py'
    files = []
    for item in primary['files']:
        name = item['path']
        if name == 'config.json':
            content = (HERE / 'config.json').read_text()
        elif (HERE / name).is_file():
            content = (HERE / name).read_text()
        else:
            content = item['content']
        files.append({'path': name, 'content': content})
    construction['files'] = files
    construction['static_checks'] = ['runner.py --check --config config.json']
    write(HERE / 'construction.json', construction)


if __name__ == '__main__':
    build()
