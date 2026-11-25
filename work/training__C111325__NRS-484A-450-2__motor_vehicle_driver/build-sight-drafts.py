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
