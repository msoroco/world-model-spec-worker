"""Build exact no-crosswalk marked-line pair from the retained source model."""
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


def replace(text, old, new):
    if old not in text:
        raise ValueError('Expected source transform missing: ' + old)
    return text.replace(old, new)


def code_for_line(files):
    runner = files['runner.py']
    runner = replace(runner, '__probe_1', '__line_stop')
    runner = replace(runner, '__probe_2', '__line_pass')
    runner = replace(runner, "case.endswith('probe_1')", "case.endswith('line_stop')")
    runner = replace(runner, "config['case_id'].endswith('probe_1')", "config['case_id'].endswith('line_stop')")
    runner = replace(runner, "or not any(o.get('type') == 'crosswalk' for o in crossings):",
                     "or any(o.get('type') == 'crosswalk' for o in crossings) or not any(o.get('name') == 'clearly_marked_stop_line' for o in crossings):")
    runner = replace(runner, 'Authored sign/crosswalk approach geometry differs',
                     'Authored sign/marked-line approach geometry differs')
    files['runner.py'] = runner
    live = files['live_capture.py']
    live = replace(live, '__probe_1', '__line_stop')
    live = replace(live, '__probe_2', '__line_pass')
    live = replace(live, "case.endswith('probe_1')", "case.endswith('line_stop')")
    live = replace(live, "'crosswalk_near_edge_y_m': -11,", "'marked_stop_line_y_m': -11,")
    files['live_capture.py'] = live
    final = files['finalize.py']
    for old, new in (
        ('from measure_stop import measure', 'from measure_stop_line import measure'),
        ('measure_crosswalk_stop', 'measure_marked_line_stop'),
        ('near_side_crosswalk_stop', 'marked_stop_line_halt'),
        ('pre_crosswalk_full_halt_observed', 'pre_line_full_halt_observed'),
        ('longest_pre_crosswalk_stop_frames', 'longest_pre_line_halt_frames'),
        ('crosswalk_stop', 'marked_line_stop'),
        ('full body halt before nearest-side crosswalk', 'full body halt before the clearly marked stop line'),
        ("if not case.startswith('training__C111325__NRS-484A-450-2__motor_vehicle_driver__probe_'):",
         "if case not in ('training__C111325__NRS-484A-450-2__motor_vehicle_driver__line_stop', 'training__C111325__NRS-484A-450-2__motor_vehicle_driver__line_pass'):"),
        ("expected = case.endswith('probe_1')", "expected = case.endswith('line_stop')"),
        ('before first full-body crosswalk entry', 'before first full-body marked-line crossing'),
        ("'st.crosswalk': lambda n, m: {'near_edge_y_m': -11, 'source': 'road.xodr',\n                                            'physical_rendering': 'unverified'},",
         "'st.crosswalk': lambda n, m: {'applicable': False, 'source': 'road.xodr'},"),
        ("'st.stop_line': lambda n, m: {'applicable': False,\n                                            'reason': 'near-side crosswalk branch; other branch pending'},",
         "'st.stop_line': lambda n, m: {'reference_y_m': -11, 'source': 'road.xodr',\n                                            'physical_rendering': 'unverified'},"),
    ):
        final = replace(final, old, new)
    files['finalize.py'] = final
    files['measure_stop_line.py'] = (HERE / 'native/measure_stop_line.py').read_text()
    files.pop('measure_stop.py')
    files['authored-road.xodr'] = (HERE / 'native/road_stop_line.xodr').read_text()
    test = files['tests/test_exact.py']
    test = replace(test, "case.endswith('probe_1')", "case.endswith('line_stop')")
    files['tests/test_exact.py'] = test
    return files


def build():
    entries = []
    for index, label in ((1, 'line_stop'), (2, 'line_pass')):
        original = json.loads((HERE / f'selected-probe-{index}-primary-construction.json').read_text())
        case_id = HERE.name + '__' + label
        files = code_for_line({entry['path']: entry['content'] for entry in original['files']})
        config = json.loads(files['config.json'])
        config['case_id'] = config['selected_case_id'] = case_id
        config['case']['case_id'] = case_id
        config['supported_case_ids'] = [HERE.name + '__line_stop', HERE.name + '__line_pass']
        config['physical_completion']['context_sources'] = ['crosswalk_geometry.json']
        files['config.json'] = json.dumps(config, indent=2) + '\n'
        construction = deepcopy(original)
        construction['case_id'] = case_id
        construction['files'] = [{'path': name, 'content': content}
                                 for name, content in sorted(files.items())]
        construction['measurement_plan'] = {'method': 'source-hashed full-body halt before a marked stop line with crosswalk absent',
                                            'status': 'selected_cpu_draft'}
        construction['static_checks'] = ['600 original frame/time joins', 'four original camera sources',
                                         'signed subject lane, no crosswalk and marked line road source']
        primary = HERE / f'selected-{label}-primary-construction.json'
        write(primary, construction)
        fallback = deepcopy(construction)
        for item in fallback['files']:
            if item['path'] == 'live_capture.py':
                item['content'] = replace(item['content'], 'START_Y = -50.0', 'START_Y = -55.0')
        alternate = HERE / f'selected-{label}-fallback1-construction.json'
        write(alternate, fallback)
        entries.append({'case_id': case_id, 'kind': 'delivery',
                        'construction': primary.name, 'construction_sha256': sha(primary),
                        'fixture_recipe': f'work/{HERE.name}/selected-{label}-fixture-recipe.json',
                        'measurement_contract': f'selected-{label}-measurement-contract.json',
                        'measurement_procedure': {'entrypoint': 'finalize.py'},
                        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                           'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
                        'candidate_risk': {'status': 'physical',
                                           'reason': 'Braking can carry the full body past a narrow marked line'},
                        'candidates': [{'id': 'fallback1', 'construction': alternate.name,
                                        'construction_sha256': sha(alternate),
                                        'changed_knobs': ['move subject spawn 5 m farther from the marked line'],
                                        'trigger': {'source': 'native_samples.jsonl',
                                                    'metric': 'first_stop_line_body_frame',
                                                    'failure_condition': 'body crosses the marked line before requested stop window'}}]})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
                'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'status': 'selected_line_cpu_draft', 'cases': entries}
    target = HERE / 'selected-line-draft-manifest.json'
    write(target, manifest)
    return {'cases': len(entries), 'manifest_sha256': sha(target)}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
