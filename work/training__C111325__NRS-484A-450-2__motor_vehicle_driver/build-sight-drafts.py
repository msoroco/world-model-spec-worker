"""Build two exact no-crosswalk/no-line sight-point CPU constructions."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, body):
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False) + '\n')


def change(value, old, new):
    if old not in value:
        raise ValueError('Sight construction transform source absent: ' + old)
    return value.replace(old, new)


def files_for_sight(files):
    runner = files['runner.py']
    runner = change(runner, '__line_stop', '__sight_stop')
    runner = change(runner, '__line_pass', '__sight_pass')
    runner = change(runner, 'line_stop', 'sight_stop')
    runner = change(runner, "or not any(o.get('name') == 'clearly_marked_stop_line' for o in crossings)",
                    "or any(o.get('name') == 'clearly_marked_stop_line' for o in crossings)")
    runner = change(runner, 'Authored sign/marked-line approach geometry differs',
                    'Authored sign/no-reference approach geometry differs')
    files['runner.py'] = runner
    live = files['live_capture.py']
    live = change(live, '__line_stop', '__sight_stop')
    live = change(live, '__line_pass', '__sight_pass')
    live = change(live, 'line_stop', 'sight_stop')
    live = change(live, "'marked_stop_line_y_m': -11,", "'sight_point_proxy_y_m': -11,")
    live = change(live, "        owned.append(ego)\n        for _ in range(30):",
                  "        owned.append(ego)\n"
                  "        moving_bp = library.find('vehicle.tesla.model3')\n"
                  "        moving_bp.set_attribute('role_name', 'c111325_intersecting_approach')\n"
                  "        traffic = world.spawn_actor(moving_bp, carla.Transform(\n"
                  "            carla.Location(x=-20.02, y=-1.75, z=2.0), carla.Rotation(yaw=0)))\n"
                  "        traffic.set_simulate_physics(False)\n"
                  "        owned.append(traffic)\n"
                  "        occluder_bp = library.find('vehicle.tesla.model3')\n"
                  "        occluder_bp.set_attribute('role_name', 'c111325_sight_occluder')\n"
                  "        occluder = world.spawn_actor(occluder_bp, carla.Transform(\n"
                  "            carla.Location(x=-4.0, y=-35.0, z=2.0), carla.Rotation(yaw=90)))\n"
                  "        occluder.set_simulate_physics(False)\n"
                  "        owned.append(occluder)\n"
                  "        for _ in range(30):")
    live = change(live,
                  "        with (output / 'native_samples.jsonl').open('x') as rows, \\\n                FrameMap(output / 'video_frames.jsonl') as frame_map:",
                  "        with (output / 'native_samples.jsonl').open('x') as rows, \\\n                (output / 'sight_samples.jsonl').open('x') as sight_rows, \\\n                FrameMap(output / 'video_frames.jsonl') as frame_map:\n            last_traffic_x = -20.02")
    live = change(live,
                  "                ego.apply_control(command(carla, ego, target, 1.75))\n                frame = world.tick()",
                  "                ego.apply_control(command(carla, ego, target, 1.75))\n"
                  "                traffic.set_transform(carla.Transform(\n"
                  "                    carla.Location(x=-20.0 + .02 * index, y=-1.75, z=2.0),\n"
                  "                    carla.Rotation(yaw=0)))\n"
                  "                frame = world.tick()")
    live = change(live, "                rows.write(json.dumps(observation, allow_nan=False) + '\\n')",
                  "                rows.write(json.dumps(observation, allow_nan=False) + '\\n')\n"
                  "                body = observation['body_vertices_m']\n"
                  "                eye = [sum(vertex[axis] for vertex in body) / 8 for axis in (0, 1)]\n"
                  "                traffic_pose = traffic.get_transform()\n"
                  "                actor = [traffic_pose.location.x, traffic_pose.location.y]\n"
                  "                velocity_x = (actor[0] - last_traffic_x) * RATE_HZ\n"
                  "                last_traffic_x = actor[0]\n"
                  "                occluder_vertices = occluder.bounding_box.get_world_vertices(occluder.get_transform())\n"
                  "                bounds = [min(v.x for v in occluder_vertices), max(v.x for v in occluder_vertices),\n"
                  "                          min(v.y for v in occluder_vertices), max(v.y for v in occluder_vertices)]\n"
                  "                ray_low = eye[1] + (bounds[0] - eye[0]) / (actor[0] - eye[0]) * (actor[1] - eye[1])\n"
                  "                ray_high = eye[1] + (bounds[1] - eye[0]) / (actor[0] - eye[0]) * (actor[1] - eye[1])\n"
                  "                low, high = sorted((ray_low, ray_high))\n"
                  "                view_open = not (high >= bounds[2] and low <= bounds[3])\n"
                  "                sight_rows.write(json.dumps({\n"
                  "                    'native_frame': frame, 'time_s': elapsed,\n"
                  "                    'approaching_traffic': actor[0] < -7 and velocity_x > 0,\n"
                  "                    'view_open': view_open, 'view_source_kind': 'native_actor_ray_proxy',\n"
                  "                    'intersecting_actor_approach': 'west_to_east',\n"
                  "                    'intersecting_actor_id': traffic.id,\n"
                  "                    'intersecting_actor_velocity_x_mps': velocity_x,\n"
                  "                    'occluder_actor_id': occluder.id,\n"
                  "                    'intersecting_actor_xy_m': actor, 'observer_eye_xy_m': eye,\n"
                  "                    'occluder_xy_bounds_m': bounds}, allow_nan=False) + '\\n')")
    live = change(live, "                   ('road.xodr', 'native_samples.jsonl')}}, indent=2) + '\\n')",
                  "                   ('road.xodr', 'native_samples.jsonl', 'sight_samples.jsonl',\n"
                  "                    'video_frames.jsonl')}}, indent=2) + '\\n')")
    files['live_capture.py'] = live
    final = files['finalize.py']
    for old, new in (
        ('from measure_stop_line import measure', 'from measure_sight_point import measure'),
        ('measure_marked_line_stop', 'measure_sight_point'),
        ('marked_stop_line_halt', 'sight_point_halt'),
        ('pre_line_full_halt_observed', 'halt_at_view_point_observed'),
        ('longest_pre_line_halt_frames', 'longest_halt_after_view_open_frames'),
        ('marked_line_stop', 'sight_point_stop'),
        ('full body halt before the clearly marked stop line', 'full body halt at the first observed view point before intersection entry'),
        ('__line_stop', '__sight_stop'), ('__line_pass', '__sight_pass'),
        ('line_stop', 'sight_stop'),
        ('before first full-body marked-line crossing', 'after first source view opening and before intersection entry'),
        ("'st.stop_line': lambda n, m: {'reference_y_m': -11, 'source': 'road.xodr',\n                                            'physical_rendering': 'unverified'},",
         "'st.stop_line': lambda n, m: {'applicable': False, 'source': 'road.xodr'},"),
        ("'st.sight_distance': lambda n, m: {'applicable': False,\n                                                 'measurement': None},",
         "'st.sight_distance': lambda n, m: {'view_open': n['sight']['view_open'],\n                                                 'source': 'sight_samples.jsonl', 'physical_review': 'pending'},"),
        ("'rel.visible': lambda n, m: {'applicable': False, 'measurement': None},",
         "'rel.visible': lambda n, m: {'view_open': n['sight']['view_open'],\n                                         'approaching_traffic': n['sight']['approaching_traffic'],\n                                         'source': 'sight_samples.jsonl', 'pixel_review': 'pending'},"),
    ):
        final = change(final, old, new)
    final = change(final,
                   "    mapping = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]",
                   "    mapping = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]\n    sight = [json.loads(line) for line in (attempt / 'sight_samples.jsonl').read_text().splitlines()]\n    if len(sight) != len(native):\n        raise ValueError('Sight source frame count differs')\n    for row, view in zip(native, sight):\n        row['sight'] = view")
    final = change(final, "'drv.crossing_line': lambda n, m: max(v[1] for v in n['body_vertices_m']) >= -11,",
                   "'drv.crossing_line': lambda n, m: n['sight']['view_open'],")
    final = change(final, "'physical_stop_sign_crosswalk_and_pixels_unverified'",
                   "'physical_stop_sign_sightline_and_pixels_unverified'")
    final = change(final, "('native_samples.jsonl', 'diagnostic-source-manifest.json',\n                                          'road.xodr', 'video_frames.jsonl', 'trace.jsonl')",
                   "('native_samples.jsonl', 'diagnostic-source-manifest.json',\n                                          'road.xodr', 'sight_samples.jsonl', 'video_frames.jsonl', 'trace.jsonl')")
    files['finalize.py'] = final
    files.pop('measure_stop_line.py')
    files['measure_sight_point.py'] = (HERE / 'native/measure_sight_point.py').read_text()
    files['authored-road.xodr'] = (HERE / 'native/road_sight_point.xodr').read_text()
    test = files['tests/test_exact.py']
    test = change(test, 'line_stop', 'sight_stop')
    files['tests/test_exact.py'] = test
    return files


def build():
    entries = []
    for label in ('stop', 'pass'):
        source = json.loads((HERE / f'selected-line_{label}-primary-construction.json').read_text())
        case_id = HERE.name + '__sight_' + label
        files = files_for_sight({item['path']: item['content'] for item in source['files']})
        config = json.loads(files['config.json'])
        config['case_id'] = config['selected_case_id'] = case_id
        config['case']['case_id'] = case_id
        config['supported_case_ids'] = [HERE.name + '__sight_stop', HERE.name + '__sight_pass']
        files['config.json'] = json.dumps(config, indent=2) + '\n'
        construction = deepcopy(source)
        construction['case_id'] = case_id
        construction['files'] = [{'path': name, 'content': content} for name, content in sorted(files.items())]
        construction['measurement_plan'] = {'method': 'source-hashed view opening with approaching intersecting traffic and body halt',
                                            'status': 'synthetic CPU draft; original driver view pending'}
        construction['static_checks'] = ['600 source frame/time joins', 'four camera sources',
                                         'no crosswalk or line in authored road',
                                         'source-hashed sight and intersecting actor observation']
        primary = HERE / f'selected-sight_{label}-primary-construction.json'
        write(primary, construction)
        fallback = deepcopy(construction)
        for item in fallback['files']:
            if item['path'] == 'live_capture.py':
                item['content'] = change(item['content'], 'START_Y = -50.0', 'START_Y = -55.0')
        alternate = HERE / f'selected-sight_{label}-fallback1-construction.json'
        write(alternate, fallback)
        entries.append({'case_id': case_id, 'kind': 'delivery',
                        'construction': primary.name, 'construction_sha256': sha(primary),
                        'fixture_recipe': f'work/{HERE.name}/selected-sight_{label}-fixture-recipe.json',
                        'measurement_contract': f'selected-sight_{label}-measurement-contract.json',
                        'measurement_procedure': {'entrypoint': 'finalize.py'},
                        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                           'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
                        'candidate_risk': {'status': 'physical',
                                           'reason': 'Braking and occlusion can shift the first view-point halt'},
                        'candidates': [{'id': 'fallback1', 'construction': alternate.name,
                                        'construction_sha256': sha(alternate),
                                        'changed_knobs': ['move subject spawn 5 m farther from sight opening'],
                                        'trigger': {'source': 'sight_samples.jsonl',
                                                    'metric': 'first_view_open_frame',
                                                    'failure_condition': 'view opens before full halt window'}}]})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
                'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'status': 'selected_sight_cpu_draft', 'cases': entries}
    target = HERE / 'selected-sight-draft-manifest.json'
    write(target, manifest)
    return {'cases': len(entries), 'manifest_sha256': sha(target)}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
