"""Materialize the assignment-root executor bundle and reviewable capture plan."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE_PREFIX = HERE.name + '__'
PRIMARY = HERE / 'night-probes/night_299_upper-construction.json'


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def build():
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    mapping = plan['source_observation_mapping']
    if isinstance(mapping, list):
        result = {}
        for item in mapping:
            term = item['term']
            value = {key: item[key] for key in item if key != 'term'}
            value['channels'] = ['headlamp_gap_ft'] if term in (
                'drv.following', 'rel.surface_gap', 'rel.ahead_behind_in_lane') else []
            result[term] = value
        plan['source_observation_mapping'] = result
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 4,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'complete subject and lead bodies, roadway surface and following interval',
             'interval': 'entire four-second original-frame interval'},
            {'view': 'approach', 'subject': 'forward lighting region and lead body',
             'interval': 'entire four-second original-frame interval'},
            {'view': 'reference_corner', 'subject': 'subject and lead body edges and roadside context',
             'interval': 'entire four-second original-frame interval'},
            {'view': 'driver_reference', 'subject': 'subject-facing forward beam and lead silhouette',
             'interval': 'entire four-second original-frame interval'}]}
    plan['review_status'] = ('Partial: all nine cases and source comparisons have synthetic CPU proofs; '
                             'actual Native motion, pixels, civil time and roadway occupancy unreviewed.')
    for row in plan['branch_inventory']:
        row['status'] = 'source_bound_synthetic_software_proved_physical_unverified'
    write(plan_path, plan)

    primary = json.loads(PRIMARY.read_text())
    selected = CASE_PREFIX + 'night_299_upper'
    config = json.loads((HERE / 'probe-config.json').read_text())
    config.update(selected_case_id=selected,
                  supported_case_ids=[entry['case_id'] for entry in plan['cases']],
                  duration_s=4, source_packets=[],
                  cameras=[{'name': name, 'width': width, 'height': height,
                            'pose_strategy': 'subject-mounted provisional source visibility view',
                            'fov_deg': fov}
                           for name, width, height, fov in (
                               ('overview', 1920, 1080, 95), ('approach', 1280, 720, 90),
                               ('reference_corner', 1280, 720, 100),
                               ('driver_reference', 1280, 720, 85))])
    config['case']['case_id'] = selected
    write(HERE / 'config.json', config)
    (HERE / 'runner.py').write_text((HERE / 'native_headlamp_probe.py').read_text())
    construction = {**primary, 'entrypoint': 'runner.py'}
    source_names = ('runner.py', 'config.json', 'headlamp_camera.py',
                    'headlamp_source_capture.py', 'headlamp_follow_route.py',
                    'headlamp_roadway_capture.py', 'headlamp_follow_measurement.py',
                    'headlamp_finalizer.py')
    construction['files'] = [{'path': name, 'content': (HERE / name).read_text()}
                             for name in source_names]
    construction['static_checks'] = ['runner.py --check --config config.json']
    write(HERE / 'construction.json', construction)


if __name__ == '__main__':
    build()
