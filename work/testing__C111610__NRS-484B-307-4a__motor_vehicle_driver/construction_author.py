"""Rebuild exact inline construction bundles from this assignment's text files."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
CASES = ('crosswalk_clear_turn', 'crosswalk_occupied_yield')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(path, bundle_path):
    return {'path': bundle_path, 'source': str(path.relative_to(REPO)),
            'content': path.read_text()}


def recording_description():
    descriptions = {
        'ego_body_heading_history': 'Original ego body, heading, speed and brake history.',
        'facing_arrow_history': 'Original ego-facing sole-arrow head and illumination frames.',
        'pedestrian_body_lawful_history': 'Original pedestrian body and sourced lawful-entry history.',
        'other_traffic_history': 'Original other-intersection-traffic inventory.',
        'crosswalk_geometry': 'Native map adjacent-crosswalk vertices.',
        'turn_route': 'Native connected left-turn waypoints.',
        'camera_frame_map': 'Synchronized original CARLA camera frame identities.'}
    channels = [{'name': name, 'unit': 'structured record', 'sampling_rate_hz': 20,
                 'method': method, 'time_window': 'arrow phase through turn clearance',
                 'reference_frame': 'CARLA world with original frame and time',
                 'uncertainty': '20 Hz sampling and Native body/map precision'}
                for name, method in descriptions.items()]
    context = [{'name': name, 'unit': 'structured record', 'method': method}
               for name, method in (
                ('intersection_context', 'Original map, official signal and route context.'),
                ('pedestrian_entry_context', 'Original Walk-phase entry or explicit clear-case absence.'))]
    return {'channels': channels, 'context_inputs': context,
            'limitations': ['Lawful entry and right-of-way require independent review.',
                            'Actual pixels and physical turn require Native review.']}


def main():
    description = recording_description()
    dispositions = json.loads((ROOT / 'case-plan.json').read_text())['requirement_dispositions']
    proposal_cases = []
    previous_path = ROOT / 'execution-manifest.json'
    previous = json.loads(previous_path.read_text()) if previous_path.is_file() else {}
    previous_entries = {e['case_id']: e for e in previous.get('cases', [])}
    entries = []
    all_ids = [ASSIGNMENT + '__' + suffix for suffix in CASES]
    proposal_cases.append({'case_id': ASSIGNMENT + '__baseline',
        'target_law_id': None, 'target_type': 'baseline',
        'rationale': 'Shared official sole-left-arrow intersection and adjacent-crosswalk geometry.',
        'variable_assignments': {'adjacent_crosswalk_occupancy': {'kind': 'world_setup',
            'value': 'clear', 'note': 'Reference world setup'},
            'arrow_direction': {'kind': 'world_setup',
            'value': 'left', 'note': 'Original official signal asset must prove arrow alone'},
            'ego_turn_controller': {'kind': 'controller', 'value': 'source_gated_left_turn',
            'note': 'Same controller for linked cases'}},
        'recording_description': description,
        'unresolved_judgment_calls': ['Lawful pedestrian entry and right-of-way review']})
    for suffix in CASES:
        folder = ROOT if suffix == CASES[0] else ROOT / 'cases' / suffix
        scene_path = folder / 'scene.json'
        scene = json.loads(scene_path.read_text())
        case_id = ASSIGNMENT + '__' + suffix
        if scene['case_id'] != case_id:
            raise ValueError('scene identity changed: ' + suffix)
        proposal_cases.append({'case_id': case_id,
            'target_law_id': scene['law_id'], 'target_type': 'boundary_probe',
            'rationale': ('Lawfully entered pedestrian occupies adjacent crosswalk during sole-arrow phase'
                          if suffix == 'crosswalk_occupied_yield' else
                          'Adjacent crosswalk remains clear during same sole-arrow left turn'),
            'variable_assignments': {
                'adjacent_crosswalk_occupancy': {'kind': 'world_setup',
                    'value': scene['crosswalk_setup'],
                    'note': 'Only deliberate comparison difference'},
                'arrow_direction': {'kind': 'world_setup', 'value': 'left',
                    'note': 'Same original official sole-arrow source'},
                'ego_turn_controller': {'kind': 'controller',
                    'value': 'source_gated_left_turn', 'note': 'Same controller'}},
            'recording_description': description,
            'unresolved_judgment_calls': ['Lawful pedestrian entry and right-of-way review'],
            'paired_probe_id': 'adjacent_crosswalk_lawful_occupancy',
            'deliberate_differences': ['adjacent_crosswalk_occupancy'],
            'probe': {'primary_variable': 'adjacent_crosswalk_occupancy',
                'comparison_or_standard': 'Original pedestrian occupancy, ego brake/entry and arrow frames; no legal cutoff',
                'target_value_or_branch': scene['crosswalk_setup']}})
        config = {'assignment_id': ASSIGNMENT, 'selected_case_id': case_id,
                  'supported_case_ids': all_ids, 'law_id': scene['law_id'],
                  'cell_id': scene['cell_id'], 'actor': scene['actor'],
                  'rate_hz': scene['rate_hz'], 'duration_s': scene['duration_s'],
                  'required_atoms': [], 'source_packets': [],
                  'cameras': [{'name': name, 'width': width, 'height': height,
                               'pose_strategy': 'ego mounted' if name == 'driver_reference'
                                                else 'fixed intersection overview',
                               'fov_deg': 90}
                              for name, width, height in (
                                ('overview', 1920, 1080), ('approach', 1280, 720),
                                ('reference_corner', 1280, 720),
                                ('driver_reference', 1280, 720))],
                  'case': {'case_id': case_id,
                           'crosswalk_setup': scene['crosswalk_setup'],
                           'recording_description': description},
                  'physical_completion': {'criterion': 'travel_progress',
                      'motion_source': 'trace.jsonl', 'position_key': 'position_m',
                      'minimum_progress_m': 5, 'minimum_samples': 2,
                      'engineering_tolerances_not_legal': True}}
        config_path = folder / 'config.json'
        write(config_path, config)
        files = [source(ROOT / name, name) for name in
                 ('runner.py', 'native_capture.py', 'analysis.py')]
        files += [source(scene_path, 'scene.json'), source(config_path, 'config.json'),
                  source(ROOT / 'tests/test_offline_case.py',
                         'tests/test_offline_case.py')]
        construction = {'law_id': scene['law_id'], 'cell_id': scene['cell_id'],
            'actor': scene['actor'], 'case_id': case_id, 'entrypoint': 'runner.py',
            'files': files, 'recording_description': description,
            'mechanisms': ['source-gated official sole left arrow and Walk entry',
                           'connected left-turn and marked adjacent-crosswalk geometry',
                           'source-hashed saved turn/yield measurements'],
            'measurement_plan': {'yield': 'Original Walk entry, lawful occupant bodies, ego brake/entry and arrow frames; no legal cutoff'},
            'static_checks': ['ego left turn crosses adjacent marked crosswalk',
                              'original facing arrow and Walk-entry source required'],
            'termination_rules': ['stop after planned 30 s or original-source failure']}
        construction_path = folder / 'construction.json'
        write(construction_path, construction)
        inputs = ['turn-history.jsonl', 'intersection-context.json', 'video_frames.jsonl']
        if suffix == 'crosswalk_occupied_yield':
            inputs.append('pedestrian-entry.jsonl')
        requirements = []
        for index, disposition in enumerate(dispositions):
            if disposition['status'] != 'selected_required' or case_id not in disposition['case_ids']:
                continue
            requirements.append({'disposition_index': index,
                'requirement': disposition['requirement'],
                'source': disposition['source'],
                'output_key': ('arrow_direction_measurement' if index == 0 else
                               'adjacent_crosswalk_yield_measurement'),
                'method': 'measure', 'value_type': 'object', 'kind': 'measured',
                'inputs': inputs})
        contract_path = folder / 'measurement-contract.json'
        removed = ('pedestrian-entry.jsonl' if suffix == 'crosswalk_occupied_yield'
                   else 'turn-history.jsonl')
        write(contract_path, {'format': 'worker-measurement-contract',
            'requirements': requirements,
            'negative': {'remove': [removed],
                         'error_contains': 'Missing required source: ' + removed}})
        relative = str(construction_path.relative_to(ROOT))
        prior = previous_entries.get(case_id, {})
        entry = {'case_id': case_id, 'kind': 'delivery',
                 'construction': relative, 'construction_sha256': sha(construction_path),
                 'candidate_risk': {'status': 'physical',
                    'reason': 'The simple bounded steering gain may not complete the connected left turn before the 30 s capture ends.'},
                 'candidates': [],
                 'measurement_contract': str(contract_path.relative_to(ROOT)),
                 'fixture_recipe': 'work/' + ASSIGNMENT + '/diagnostic-' + suffix + '-recipe.json',
                 'measurement_procedure': {'entrypoint': 'analysis.py'},
                 'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                    'host_env_var': 'CARLA_HOST',
                                    'port_env_var': 'CARLA_PORT'}}
        if prior.get('construction_sha256') == entry['construction_sha256']:
            entry.update({key: prior[key] for key in
                ('offline', 'physical_preparation', 'candidate_risk', 'candidates',
                 'compatibility', 'post_capture', 'delivery_acceptance')
                if key in prior})
        entries.append(entry)
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'cases': entries}
    write(previous_path, manifest)
    write(ROOT / 'proposals/cases.json', {'cell_id': 'C111610',
        'actor': 'motor_vehicle_driver', 'status': 'draft',
        'cases': proposal_cases, 'sweep_specs': [{
            'sweep_id': 'c111610-lawful-adjacent-yield',
            'target_law_id': 'NRS-484B-307-4a',
            'judgment_refs': [{'phrase': 'yield the right-of-way to pedestrians lawfully within the adjacent crosswalk',
                'note': 'The exact law supplies no numeric yielding or lawful-presence cutoff.'}],
            'status': 'incomplete',
            'rationale': 'Original signal/crosswalk asset and feasible nontransient pedestrian/ego timing range are not supplied.',
            'missing_inputs': ['Source-backed official sole-arrow and marked crosswalk asset',
                'Feasible nontransient approach, entry and clearance range across turning encounter']}],
        'sweeps_expanded': True})


if __name__ == '__main__':
    main()
