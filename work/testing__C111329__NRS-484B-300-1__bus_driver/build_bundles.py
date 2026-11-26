"""Build four exact source-gated bundles and synthetic compatibility recipes."""
import copy
import hashlib
import json
from pathlib import Path

from package_spec import ACTOR, AID, CAMERAS, CASES, CELL, HERE, LAW, RECORDING, ROOT, case_id

DONOR = ROOT / 'work/testing__C149470__LVMC-11-60-030-A4__bus_driver/diagnostics'
DONOR_CASE = DONOR / 'bus_stop_below'
SOURCE_NAMES = ('trace.jsonl', 'video_frames.jsonl',
                'capture/native/frames.jsonl', 'capture/evidence.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False,
                               separators=(',', ':') if compact else None,
                               indent=None if compact else 2) + '\n')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('returned file exceeds 2 MiB: ' + str(path))


def source(path, target):
    return {'path': target, 'source': str(path.relative_to(ROOT)), 'sha256': sha(path)}


def construction(name, aspect, policy, direction, enter, candidate):
    cid = case_id(name)
    profile = {'hold_brake_scale': 1.2 if candidate == 'fallback1' and not enter else 1.0,
               'proceed_throttle_scale': 1.2 if candidate == 'fallback1' and enter else 1.0}
    config = {'law_id': LAW, 'cell_id': CELL, 'actor': ACTOR,
              'selected_case_id': cid, 'candidate_id': candidate,
              'rate_hz': 20, 'duration_s': 45, 'required_atoms': [], 'source_packets': [],
              'cameras': CAMERAS, 'supported_case_ids': [case_id(row[0]) for row in CASES],
              'case': {'case_id': cid, 'kind': name, 'device_aspect': aspect,
                       'bus_control_policy': policy, 'police_direction': direction,
                       'line_entry_request': enter, 'control_profile': profile,
                       'recording_description': RECORDING}}
    sources = ('runner.py', 'package_spec.py', 'device_scene.py', 'device_control.py',
               'native_capture.py', 'reviewed_source.py', 'analysis.py',
               'comparison_audit.py')
    files = [{'path': name, 'content': (HERE / name).read_text()} for name in sources]
    files += [{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
              {'path': 'tests/test_bundle.py',
               'content': (HERE / 'diagnostic_bundle_test.py').read_text()}]
    return {'law_id': LAW, 'cell_id': CELL, 'actor': ACTOR, 'case_id': cid,
            'candidate_id': candidate, 'entrypoint': 'runner.py',
            'files': files, 'recording_description': RECORDING,
            'measurement_plan': {'case_id': cid, 'procedure': 'analysis.py',
                                 'original_frames': 900, 'legal_verdict': 'unresolved'},
            'static_checks': ['exact bus, governing device and reviewed route identity',
                              '900 joined original device, bus and camera frames'],
            'termination_rules': ['900 original frames at 20 Hz',
                                  'fail closed on missing reviewed source or frame join'],
            'mechanisms': ['source-gated Native bus construction and readback',
                           'original device history and bus-front stop-line measurement',
                           'source-sealed four-camera Native capture']}


def build():
    note = HERE / 'diagnostic-source-note.json'
    put(note, {'format': 'c111329-synthetic-source-note-v1',
               'source_kind': 'synthetic_diagnostic_fixture',
               'accepted_original_source': False, 'physical_acceptance': False,
               'legal_verdict': None})
    donor_generator = json.loads((DONOR / 'bus_stop_below-generator.json').read_text())
    entries = []
    for name, aspect, policy, direction, enter in CASES:
        cid = case_id(name)
        folder = HERE / 'diagnostics' / name
        folder.mkdir(parents=True, exist_ok=True)
        for filename in SOURCE_NAMES:
            target = folder / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((DONOR_CASE / filename).read_bytes())
        mock_sources = []
        for item in ('map', 'device', 'route', 'authority'):
            target = folder / (item + '-source.json')
            put(target, {'synthetic_fixture': True, 'source_kind': item,
                         'case_id': cid, 'accepted_original_source': False})
            mock_sources.append({'path': target.name, 'sha256': sha(target)})
        site = {'cell_id': CELL, 'actor': ACTOR, 'native_map_name': 'TownSurvey',
                'device_id': 17, 'ego_approach_id': 'north',
                'governs_ego_approach': True, 'original_sources': mock_sources,
                'map_source_path': 'map-source.json',
                'device_source_path': 'device-source.json',
                'route_source_path': 'route-source.json',
                'authority_source_path': 'authority-source.json',
                'bus_route_xy': [[0, 0], [10, 0], [20, 0]],
                'stop_line_xy': [8, 0], 'bus_clearance_width_m': 3.5,
                'bus_body_width_m': 2.6, 'bus_clearance_height_m': 4.3,
                'bus_body_height_m': 3.4, 'bus_blueprint_id': 'vehicle.bus',
                'spawn_z_m': .5, 'approach_yaw_deg': 0,
                'hold_brake': .7, 'proceed_throttle': .25}
        put(folder / 'site.json', site)
        rows = []
        for index in range(900):
            x = 7 * min(index / 150, 1) if not enter else 20 * min(index / 350, 1)
            rows.append({'frame': 100 + index, 'device_id': 17,
                         'facing_approach_id': 'north', 'bus_actor_id': 42,
                         'bus_blueprint_id': 'vehicle.bus', 'aspect': aspect,
                         'bus_front_xy': [x, 0], 'police_direction': direction,
                         'police_direction_source': 'authority-source.json' if direction else None,
                         'placement_source': 'device-source.json',
                         'nrs_307_context_source': 'authority-source.json'})
        put(folder / 'device-rows.json', rows, compact=True)
        put(folder / 'acquisition-provenance.json',
            {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True})
        sources = [source(folder / filename, filename) for filename in SOURCE_NAMES]
        sources += [source(folder / name, name) for name in
                    ('site.json', 'device-rows.json', 'acquisition-provenance.json',
                     'map-source.json', 'device-source.json',
                     'route-source.json', 'authority-source.json')]
        sources.append(source(note, 'diagnostic-source-note.json'))
        generator = copy.deepcopy(donor_generator)
        generator['files']['capture/manifest.json'] = json.dumps({
            'acquisition': 'synthetic_fixture', 'case_id': cid,
            'extraction_confirmed': True, 'frames': 900,
            'observation_contract_version': 2, 'required_observations': [],
            'complete_driving_lanes': True,
            'native_map_facts': {'path': 'native_map_facts.json',
                                 'sha256': hashlib.sha256(generator['files']['capture/native_map_facts.json'].encode()).hexdigest()},
            'sources': {'road.xodr': hashlib.sha256(generator['files']['road.xodr'].encode()).hexdigest(),
                        'trace.jsonl': sha(folder / 'trace.jsonl')}}, indent=2) + '\n'
        generator_path = HERE / 'diagnostics' / (name + '-generator.json')
        put(generator_path, generator, compact=True)
        recipe = HERE / 'diagnostics' / (name + '-recipe.json')
        put(recipe, {'format': 'worker-fixture-recipe', 'sources': sources,
                     'generator': {'source': str(generator_path.relative_to(ROOT)),
                                   'sha256': sha(generator_path)}})
        primary = construction(name, aspect, policy, direction, enter, 'primary')
        fallback = construction(name, aspect, policy, direction, enter, 'fallback1')
        primary_path = HERE / 'cases' / name / 'construction.json'
        fallback_path = HERE / 'cases' / name / 'fallback1' / 'construction.json'
        put(primary_path, primary)
        put(fallback_path, fallback)
        requirements = []
        plan = json.loads((HERE / 'case-plan.json').read_text())
        for index, disposition in enumerate(plan['requirement_dispositions']):
            if cid not in disposition.get('case_ids', []):
                continue
            requirements.append({'disposition_index': index,
                                 'requirement': disposition['requirement'],
                                 'source': disposition['source'],
                                 'output_key': ('official_device_measurement', 'bus_conduct_measurement',
                                                'police_direction_measurement', 'nrs_307_context_measurement')[index],
                                 'method': ('measure_device_history', 'measure_bus_conduct',
                                            'measure_police_direction', 'measure_exception_context')[index],
                                 'value_type': 'object', 'kind': 'measured' if index < 2 else 'sourced_context',
                                 'inputs': ['device-rows.json', 'site.json', 'diagnostic-source-note.json']})
        contract = HERE / 'diagnostics' / (name + '-measurement-contract.json')
        put(contract, {'format': 'worker-measurement-contract', 'case_id': cid,
                       'requirements': requirements,
                       'negative': {'remove': ['device-rows.json'],
                                    'error_contains': 'Missing required source: device-rows.json'}})
        acquisition = {channel['name']: {'entrypoint': 'analysis.py',
                                         'method': channel['method'],
                                         'evidence': 'channel-' + channel['name'] + '.jsonl'}
                       for channel in RECORDING['channels']}
        entries.append({'case_id': cid, 'kind': 'delivery',
                        'construction': str(primary_path.relative_to(HERE)),
                        'construction_sha256': sha(primary_path),
                        'fixture_recipe': str(recipe.relative_to(ROOT)),
                        'measurement_contract': str(contract.relative_to(HERE)),
                        'measurement_procedure': {'entrypoint': 'analysis.py'},
                        'acquisition': acquisition,
                        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                           'host_env_var': 'CARLA_HOST',
                                           'port_env_var': 'CARLA_PORT'},
                        'source_gate': 'reviewed original official device, bus route, officer and 307 context required',
                        'candidate_risk': 'red hold may overshoot the surveyed line; proceeding bus may fail to cross within the 45-second window',
                        'candidates': [{'id': 'fallback1',
                                        'construction': str(fallback_path.relative_to(HERE)),
                                        'construction_sha256': sha(fallback_path),
                                        'trigger': {'metric': 'original bus-front signed distance to surveyed line',
                                                    'source': 'original Native device/bus history',
                                                    'failure_condition': 'red hold overshoots line or intended proceed fails to enter'},
                                        'changed_knobs': ['controller hold brake scale +20 percent' if not enter else 'controller proceed throttle scale +20 percent']}],
                        'offline': {'construction_sha256': sha(primary_path),
                                    'command': None, 'exit_code': None,
                                    'log': None, 'log_sha256': None}})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
                'status': 'source_gated_selected_draft',
                'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'cases': entries}
    put(HERE / 'execution-manifest.json', manifest)
    print('exact selected bundles and recipes:', len(entries))


if __name__ == '__main__':
    build()
