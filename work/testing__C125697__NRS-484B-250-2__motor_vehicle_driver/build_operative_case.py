"""Build the operative-signal comparison with distinct Native control and analysis."""
import copy
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'cases/operative_signal'
LEFT = HERE.name + '__off_ego_left_near_time'
CASE = HERE.name + '__operative_signal'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Expected exactly one source location: ' + old[:70])
    return source.replace(old, new)


def variant_sources(files):
    signal = files['signal_control.py'] + '''\n\n@contextmanager
def request_operative(world, lights, traffic_light_state):
    if len(lights) < 2 or len({light.id for light in lights}) != len(lights):
        raise ValueError('Distinct inventoried entrance lights required')
    original = []
    expected = [traffic_light_state.Red, traffic_light_state.Green] + [traffic_light_state.Red] * (len(lights) - 2)
    try:
        for light, target in zip(lights, expected):
            original.append((light, light.get_state()))
            light.freeze(True)
            light.set_state(target)
        world.tick()
        if [light.get_state() for light in lights] != expected:
            raise ValueError('Operative Native signal readback failed')
        yield lights
    finally:
        for light, state in reversed(original):
            light.set_state(state)
            light.freeze(False)
        if original:
            world.tick()
            if any(light.get_state() != state for light, state in original):
                raise ValueError('Native signal restoration readback failed')
'''
    controlled = files['controlled_pair.py']
    controlled = replace_once(controlled, 'find_entrance_lights, request_all_off',
                              'find_entrance_lights, request_operative')
    controlled = replace_once(controlled, 'def construct_off_pair(',
                              'def construct_operational_pair(')
    controlled = replace_once(controlled, 'with request_all_off(world, lights, traffic_light_state):',
                              'with request_operative(world, lights, traffic_light_state):')
    controlled = replace_once(controlled, '    lights = find_entrance_lights(world, lanes)',
                              "    if (lanes[0] != (plan['approaches']['ego']['road_id'], plan['approaches']['ego']['lane_id']) or\n"
                              "            lanes[1] != (plan['approaches']['other']['road_id'], plan['approaches']['other']['lane_id'])):\n"
                              "        raise ValueError('Operative head inventory must map ego then other')\n"
                              '    lights = find_entrance_lights(world, lanes)')
    runner = files['runner.py'].replace(LEFT, CASE)
    runner = replace_once(runner, 'from controlled_pair import construct_off_pair',
                          'from controlled_pair import construct_operational_pair')
    runner = replace_once(runner, 'with construct_off_pair(',
                          'with construct_operational_pair(')
    runner = replace_once(runner,
                          "if config.get('rate_hz') != 20 or config.get('duration_s') != 45:",
                          "if config.get('signal_mode') != 'operative_ego_red_other_green':\n"
                          "        raise ValueError('Operative signal mode required')\n"
                          "    if config.get('rate_hz') != 20 or config.get('duration_s') != 45:")
    capture = files['capture_sources.py']
    capture = replace_once(capture,
                           'if any(state != traffic_light_state.Off for state in states):\n'
                           "        raise ValueError('All inventoried entrance lights must read back Off')",
                           'expected = [traffic_light_state.Red, traffic_light_state.Green] + [traffic_light_state.Red] * (len(lights) - 2)\n'
                           '    if states != expected:\n'
                           "        raise ValueError('Operative entrance lights must read back Red/Green')")
    capture = replace_once(capture,
                           "'governing_signal_state': 'Off',\n"
                           "           'entrance_signal_states': [{'actor_id': light.id, 'state': 'Off'} for light in lights],",
                           "'governing_signal_state': 'Red',\n"
                           "           'entrance_signal_states': [{'actor_id': light.id, 'state': 'Green' if i == 1 else 'Red'}\n"
                           "                                      for i, light in enumerate(lights)],")
    capture = replace_once(capture,
                           "'opposite_approach_with_left_turn': False,",
                           "'opposite_approach_with_left_turn': False,\n"
                           "            'official_device_operating': True,")
    entries = replace_once(files['simultaneous_entries.py'],
                           'if row.get("governing_signal_state")!="Off":\n'
                           '            raise ValueError("Governing Native signal not observed Off")',
                           'if row.get("governing_signal_state")!="Red":\n'
                           '            raise ValueError("Governing Native signal not observed operative Red")')
    finalizer = files['finalizer.py'].replace(LEFT, CASE)
    begin = finalizer.index('def measure_signal_context(')
    end = finalizer.index('\ndef measure_opposite_turn_context(', begin)
    signal_measure = '''def measure_signal_context(context, history):
    if context.get('official_device_operating') is not True:
        raise ValueError('Operative device context required')
    if not history or any(row.get('governing_signal_state') != 'Red' or
                          not isinstance(row.get('entrance_signal_states'), list) or
                          len(row['entrance_signal_states']) < 2 or
                          [head.get('state') for head in row['entrance_signal_states']] !=
                          ['Red', 'Green'] + ['Red'] * (len(row['entrance_signal_states']) - 2)
                          for row in history):
        raise ValueError('Inventoried entrance heads must be operative Red/Green at original frames')
    first_ids = [head.get('actor_id') for head in history[0]['entrance_signal_states']]
    if (any(identifier is None for identifier in first_ids) or
            len(set(first_ids)) != len(first_ids) or
            any([head.get('actor_id') for head in row['entrance_signal_states']] != first_ids
                for row in history)):
        raise ValueError('Stable distinct entrance head identities required')
    return {'captured_entrance_head_count': len(first_ids),
            'captured_entrance_head_ids': first_ids,
            'all_sampled_states_operative': True,
            'ego_governing_state': 'Red', 'other_governing_state': 'Green',
            'all_entrances_source': context['all_entrances_source'],
            'signal_governance_source': context['signal_governance_source'],
            'signal_head_video_source': context['signal_head_video_source'],
            'official_device_exclusion_judgment': 'unresolved',
            'subsection_4_judgment': 'unresolved'}

'''
    finalizer = finalizer[:begin] + signal_measure + finalizer[end:]
    finalizer = replace_once(finalizer,
                             "config.get('selected_case_id') != PRIMARY or",
                             "config.get('selected_case_id') != PRIMARY or\n"
                             "            config.get('signal_mode') != 'operative_ego_red_other_green' or")
    finalizer = finalizer.replace('All inventoried entrance heads must be Off at original frames',
                                  'Inventoried entrance heads must be operative Red/Green at original frames')
    return {'runner.py': runner, 'signal_control.py': signal,
            'controlled_pair.py': controlled, 'capture_sources.py': capture,
            'simultaneous_entries.py': entries, 'finalizer.py': finalizer}


def build():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if any(row['case_id'] == CASE for row in manifest['cases']):
        raise ValueError('Operative case already constructed; retain bound proofs')
    bundle = copy.deepcopy(json.loads((HERE / 'construction.json').read_text()))
    files = {row['path']: row['content'] for row in bundle['files']}
    cfg = json.loads(files['config.json'])
    cfg['selected_case_id'] = CASE
    cfg['signal_mode'] = 'operative_ego_red_other_green'
    spec = importlib.util.spec_from_file_location('test_runner', HERE / 'tests/test_runner.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as temporary:
        site_dir = Path(temporary)
        module.write_review(site_dir, cfg)
        packet = {path.name: path.read_text() for path in site_dir.iterdir() if path.is_file()}
    variants = variant_sources(files)
    OUT.mkdir(parents=True, exist_ok=True)
    variants['config.json'] = json.dumps(cfg, indent=2, allow_nan=False) + '\n'
    variants.update(packet)
    for name, content in variants.items():
        (OUT / name).write_text(content)
    for row in bundle['files']:
        if row['path'] in variants:
            row['content'] = variants[row['path']]
            row['source'] = str((OUT / row['path']).relative_to(HERE.parents[1]))
    bundle['case_id'] = CASE
    bundle['status'] = 'synthetic_diagnostic_only'
    path = OUT / 'construction.json'
    path.write_text(json.dumps(bundle, indent=2, allow_nan=False) + '\n')
    manifest['cases'].append({
        'case_id': CASE, 'kind': 'delivery', 'construction': str(path.relative_to(HERE)),
        'construction_sha256': sha(path),
        'measurement_procedure': {'entrypoint': 'finalizer.py'},
        'measurement_contract': str((OUT / 'measurement-contract.json').relative_to(HERE)),
        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                           'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
        'candidate_risk': {'status': 'physical',
                           'reason': 'Native operative head mapping or readback, approach coverage and entry timing may fail.'},
        'candidates': [],
    })
    manifest['status'] = 'partial_four_case_operative_construction'
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    return {'case_id': CASE, 'construction_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
