"""Materialize an opposite-direction left-turn candidate without changing proven cases.

This is a CPU construction checkpoint. It does not claim a physical site or
append the case to the execution manifest until the saved path is proven.
"""
import importlib.util
import copy
import hashlib
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'cases/off_opposite_left_turn'
CASE = HERE.name + '__off_opposite_left_turn'
LEFT = HERE.name + '__off_ego_left_near_time'


def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Expected one source clause: ' + old[:65])
    return source.replace(old, new)


def variants():
    native = (HERE / 'native_pair.py').read_text()
    native = once(native,
                  "if site['ego_highway_id'] == site['other_highway_id']:\n"
                  "        raise ValueError('Different source highway identities required')",
                  "if site['ego_highway_id'] != site['other_highway_id']:\n"
                  "        raise ValueError('Opposite approaches must use one sourced highway')")
    native = once(native,
                  "if approaches['ego']['road_id'] == approaches['other']['road_id']:\n"
                  "        raise ValueError('Distinct Native approach roads required')",
                  "if (approaches['ego']['road_id'] != approaches['other']['road_id'] or\n"
                  "        approaches['ego']['lane_id'] == approaches['other']['lane_id']):\n"
                  "        raise ValueError('Opposite approaches need one Native road and distinct lanes')")
    native = once(native,
                  "if side not in ('right', 'left', 'opposite'):",
                  "if side != 'opposite':")

    runner = (HERE / 'runner.py').read_text().replace(LEFT, CASE)
    runner = once(runner,
                  "if config.get('other_approach_side') != 'right':\n"
                  "        raise ValueError('Other approach must be on ego right for ego-left case')",
                  "if config.get('other_approach_side') != 'opposite':\n"
                  "        raise ValueError('Opposite approach required')")
    runner = once(runner,
                  "site['ego_highway_id'] == site['other_highway_id'] or",
                  "site['ego_highway_id'] != site['other_highway_id'] or")
    runner = once(runner,
                  "raise ValueError('One sourced crossing of distinct highways required')",
                  "raise ValueError('One sourced crossing on an opposite-direction highway required')")
    runner = once(runner,
                  "    for role in ('ego', 'other'):\n"
                  "        validate_route(routes[role], site[role + '_approach'][:2],\n"
                  "                       site[role + '_entry'][:2], polygon, role)",
                  "    for role in ('ego', 'other'):\n"
                  "        validate_route(routes[role], site[role + '_approach'][:2],\n"
                  "                       site[role + '_entry'][:2], polygon, role)\n"
                  "    if (routes['other'][-1][1] >= polygon[0][1] or\n"
                  "            routes['other'][1][0] >= routes['other'][0][0]):\n"
                  "        raise ValueError('Other route must enter westbound then exit southbound left')")

    packet = (HERE / 'site_packet.py').read_text()
    packet = once(packet,
                  "site['ego_highway_id'] == site['other_highway_id'] or",
                  "site['ego_highway_id'] != site['other_highway_id'] or")
    packet = once(packet,
                  "raise ValueError('One sourced crossing of distinct highways required')",
                  "raise ValueError('One sourced crossing on an opposite-direction highway required')")

    capture = (HERE / 'capture_sources.py').read_text()
    capture = once(capture,
                   "'opposite_approach_with_left_turn': False,",
                   "'opposite_approach_with_left_turn': True,\n"
                   "            'other_left_turn_route_xy_m': site['routes']['other'],")

    entries = (HERE / 'simultaneous_entries.py').read_text()
    entries = once(entries,
                   'if ctx["ego_highway_id"]==ctx["other_highway_id"]:',
                   'if ctx["ego_highway_id"]!=ctx["other_highway_id"]:')

    finalizer = (HERE / 'finalizer.py').read_text().replace(LEFT, CASE)
    finalizer = once(finalizer,
                     'from simultaneous_entries import analyze',
                     'from simultaneous_entries import analyze\n'
                     'from opposite_turn_measurement import measure_opposite_turn_context')
    begin = finalizer.index('def measure_opposite_turn_context(')
    end = finalizer.index('\ndef measure_yield_observation(', begin)
    finalizer = finalizer[:begin] + finalizer[end + 1:]
    finalizer = once(finalizer,
                     'measure_opposite_turn_context(context),\n'
                     "                                       ['junction_context.json']),",
                     'measure_opposite_turn_context(context, history, controls),\n'
                     "                                       ['junction_context.json', 'crossing_history.jsonl',\n"
                     "                                        'controller_history.jsonl']),")
    contract = json.loads((HERE / 'measurement-contract.json').read_text())
    for item in contract['requirements']:
        if item['output_key'] == 'opposite_left_turn_context':
            item['kind'] = 'measured'
            item['inputs'] = ['junction_context.json', 'crossing_history.jsonl',
                              'controller_history.jsonl']
            item['requirement'] = 'Opposite-direction left-turn intent and original motion/steering are retained'
            break

    cfg = json.loads((HERE / 'config.json').read_text())
    cfg['selected_case_id'] = CASE
    cfg['other_approach_side'] = 'opposite'
    site = cfg['site']
    site['other_highway_id'] = site['ego_highway_id']
    site['ego_approach'] = [0, -1.75, 0, 0]
    site['ego_entry'] = [12, -1.75, 0, 0]
    site['other_approach'] = [30, 1.75, 0, 180]
    site['other_entry'] = [18, 1.75, 0, 180]
    site['routes'] = {
        'ego': [[0, -1.75], [12, -1.75], [15, -1.75], [24, -1.75]],
        'other': [[30, 1.75], [18, 1.75], [15, 1.75], [15, -12]],
    }
    site['entrance_road_lanes'] = [[1, -1], [1, 1]]
    cfg['recording_description']['limitations'] = [
        'Synthetic site and route; no physical or statutory acceptance',
        'Opposite-direction left-turn exception remains a legal judgment',
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    for name, contents in {'native_pair.py': native, 'runner.py': runner,
                           'site_packet.py': packet, 'capture_sources.py': capture,
                           'simultaneous_entries.py': entries,
                           'finalizer.py': finalizer}.items():
        (OUT / name).write_text(contents)
    (OUT / 'measurement-contract.json').write_text(json.dumps(contract, indent=2) + '\n')
    spec = importlib.util.spec_from_file_location('test_runner', HERE / 'tests/test_runner.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as temp:
        module.write_review(Path(temp), cfg)
        for source in Path(temp).iterdir():
            (OUT / source.name).write_bytes(source.read_bytes())
    (OUT / 'config.json').write_text(json.dumps(cfg, indent=2) + '\n')
    construction = copy.deepcopy(json.loads((HERE / 'construction.json').read_text()))
    construction['case_id'] = CASE
    construction['recording_description'] = cfg['recording_description']
    replacement_names = {p.name for p in OUT.iterdir() if p.is_file()}
    seen = set()
    for item in construction['files']:
        name = item['path']
        if name in replacement_names:
            item['content'] = (OUT / name).read_text()
            item['source'] = str((OUT / name).relative_to(HERE.parents[1]))
            seen.add(name)
    for name in sorted(replacement_names - seen - {'construction.json', 'candidate-manifest.json',
                                                    'measurement-contract.json'}):
        construction['files'].append({'path': name, 'content': (OUT / name).read_text(),
                                      'source': str((OUT / name).relative_to(HERE.parents[1]))})
    construction['status'] = 'synthetic_diagnostic_only'
    construction_path = OUT / 'construction.json'
    construction_path.write_text(json.dumps(construction, indent=2, allow_nan=False) + '\n')
    digest = hashlib.sha256(construction_path.read_bytes()).hexdigest()
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    manifest['cases'].append({
        'case_id': CASE, 'kind': 'delivery',
        'construction': 'construction.json',
        'construction_sha256': digest,
        'measurement_procedure': {'entrypoint': 'finalizer.py'},
        'measurement_contract': 'measurement-contract.json',
        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                           'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
        'candidate_risk': {'status': 'physical',
                           'reason': 'Opposite approach lane and actual left turn may fail in Native motion.'},
        'candidates': []})
    (OUT / 'candidate-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return OUT


if __name__ == '__main__':
    print(variants())
