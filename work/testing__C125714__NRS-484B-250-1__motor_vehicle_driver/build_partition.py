"""Derive the six partition-02 packages from this checkout's frozen inputs."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).resolve().parent
RUNTIME = ROOT / 'runtime/main-pipeline-v1'
SKILL = ROOT / 'skills/worker-preparation/SKILL.md'
IDS = json.loads((ROOT / 'partitions/demo-test-02.json').read_text())['assignment_ids']

SPECS = {
    'NRS-484B-250-1': {'mode': 'crossing_priority', 'cases': [
        ('prior_entry_yield', {'yield_command': (True, 'categorical'), 'ego_delay_s': (1.2, 's')}),
        ('prior_entry_no_yield', {'yield_command': (False, 'categorical'), 'ego_delay_s': (1.2, 's')})],
        'difference': 'same other-first entry with ego yield command versus no yield command',
        'gap': 'Native incoming-lane and device-governance inventory needs closed original execution; legal precedence and subsection-4 qualification remain unjudged.'},
    'NRS-484B-250-2': {'mode': 'crossing_priority', 'cases': [
        ('release_delay_0_0', {'ego_delay_s': (0.0, 's'), 'yield_command': (True, 'categorical')}),
        ('release_delay_0_5', {'ego_delay_s': (.5, 's'), 'yield_command': (True, 'categorical')}),
        ('release_delay_1_0', {'ego_delay_s': (1.0, 's'), 'yield_command': (True, 'categorical')})],
        'difference': 'ego release delay 0.0, 0.5, or 1.0 s; measure original entry time difference without choosing a legal simultaneity tolerance',
        'gap': 'Statutory approximately-same-time standard and subsection-4 qualification remain unresolved; native incoming-lane inventory needs closed original execution.'},
    'NRS-484B-227-1': {'mode': 'divider_turn', 'cases': [
        ('opening_direct', {'path_kind': ('opening_direct', 'categorical')}),
        ('divider_crossing', {'path_kind': ('divider_crossing', 'categorical')}),
        ('opening_multiple', {'path_kind': ('opening_multiple', 'categorical')})],
        'difference': 'opening traversal, divider crossing outside opening, and multiple-movement opening route',
        'gap': 'Pinned Core st.median_or_divider adapter path is absent; barrier collision, public-authority establishment and multiple-movement physics await native execution.'},
    'NRS-484B-220-1': {'mode': 'oneway', 'cases': [
        ('designated_direction', {'direction': ('designated', 'categorical')}),
        ('opposite_direction', {'direction': ('opposite', 'categorical')})],
        'difference': 'eastbound designated versus westbound opposite travel on the same authored two-lane roadway',
        'gap': 'Pinned Core st.one_way_roadway and dev.regulatory_sign adapter paths are absent; sign authority and placement need native evidence.'},
    'NRS-484B-600-1a': {'mode': 'speed', 'cases': [
        ('speed_05', {'commanded_speed_mps': (5.0, 'm/s')}),
        ('speed_10', {'commanded_speed_mps': (10.0, 'm/s')}),
        ('speed_15', {'commanded_speed_mps': (15.0, 'm/s')}),
        ('speed_20', {'commanded_speed_mps': (20.0, 'm/s')})],
        'difference': 'commanded speed 5, 10, 15, or 20 m/s with traffic and road conditions held fixed',
        'gap': 'Pinned Core env.ice_or_snow and env.visibility adapter paths are absent; actual material inventory and full highway-condition observation remain unverified.'},
    'NRS-484B-413-2': {'mode': 'signal', 'cases': [
        ('onset_090ft', {'signal_onset_ft': (90.0, 'ft')}),
        ('onset_100ft', {'signal_onset_ft': (100.0, 'ft')}),
        ('onset_110ft', {'signal_onset_ft': (110.0, 'ft')})],
        'difference': 'right indicator command begins 90, 100, or 110 ft before course change; measure original path and rendered lamp phases',
        'gap': 'Pinned Core sig.hand_signal path is absent; this package tests the right-indicator alternative and must measure actual lamp phase and district frontage in a native run.'},
}


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def channel(name):
    unit = {'kin.heading': 'deg', 'kin.speed': 'm/s', 'kin.path_length': 'm',
            'env.precipitation': '%', 'env.wet_road': '%'} .get(name, 'structured')
    method = {
        'kin.position': 'original actor world XYZ each recorded tick',
        'kin.heading': 'original actor world yaw each recorded tick',
        'kin.speed': 'original actor velocity norm each recorded tick',
        'kin.velocity': 'original actor velocity vector each recorded tick',
        'kin.path_length': 'cumulative distance from original actor positions',
        'sig.turn_indicator': 'original actor.get_light_state bitmask plus separately decoded RGB lamp phase',
        'env.precipitation': 'same-frame native world weather precipitation',
        'env.wet_road': 'same-frame native world weather wetness',
        'env.visibility': 'pre-recording native RGB/instance contrast calibration plus same-frame atmosphere readback',
        'env.ice_or_snow': 'native surface material/object inventory; unresolved if no verified material path',
    }.get(name)
    if method is None:
        method = ('same-frame native map projection, topology and source actor/device inventory' if
                  name.startswith(('st.', 'dev.')) else
                  'original same-frame actor bodies, positions and source geometry' if name.startswith('rel.') else
                  'original same-frame actor pose, control, path and counterpart state; legal decision unresolved')
    return {'name': name, 'unit': unit, 'sampling_rate_hz': 20, 'method': method,
            'time_window': 'all original recorded ticks', 'reference_frame': 'CARLA world/native map',
            'uncertainty': 'finite original samples; physical and legal status unverified'}


def package(aid):
    folder = ROOT / 'work' / aid
    folder.mkdir(parents=True, exist_ok=True)
    assignment_path = ROOT / 'inputs' / aid / 'assignment.json'
    assignment = json.loads(assignment_path.read_text())
    law = assignment['law_id']; spec = SPECS[law]; mode = spec['mode']
    sys.path.insert(0, str(SOURCE))
    from scene_model import build_xodr, route
    (folder / 'scene.xodr').write_text(build_xodr(mode))
    for name in ('runner.py', 'analyze.py', 'scene_model.py'):
        if folder / name != SOURCE / name:
            shutil.copyfile(SOURCE / name, folder / name)
    (folder / 'tests').mkdir(exist_ok=True)
    if folder / 'tests/test_package.py' != SOURCE / 'tests/test_package.py':
        shutil.copyfile(SOURCE / 'tests/test_package.py', folder / 'tests/test_package.py')
    names = list(dict.fromkeys(['kin.position', 'kin.heading', 'kin.speed'] +
            [t['term'] for t in assignment['source_observation_terms']]))
    description = {'channels': [channel(name) for name in names], 'context_inputs': [],
        'limitations': ['Synthetic public-way/device authority needs external confirmation.',
                        'Diagnostic fixtures do not prove motion, duration, visibility, signal rendering or legal standards.']}
    cases = []
    for label, variation in spec['cases']:
        cases.append({'case_id': aid + '__' + label, 'target_law_id': law,
            'target_type': 'boundary_probe',
            'rationale': spec['difference'],
            'variable_assignments': {key: {'value': value, 'unit': unit, 'kind': 'controller'}
                                     for key, (value, unit) in variation.items()},
            'unresolved_judgment_calls': [spec['gap'], 'No legal compliance label is assigned.'],
            'recording_description': description})
    proposal = {'status': 'draft', 'cell_id': assignment['cell_id'], 'actor': assignment['actor'],
                'sweep_specs': [], 'cases': cases}
    write(folder / 'proposals/cases.json', proposal)
    mapping = {term['term']: {'evidence': channel(term['term'])['method'],
                             'channels': [term['term']],
                             'source_refs': ['capture/evidence.jsonl', 'road.xodr']}
               for term in assignment['source_observation_terms']}
    plan = {'assignment_id': aid, 'actor': assignment['actor'], 'cell_id': assignment['cell_id'],
            'law_id': law, 'cases': cases,
            'comparisons': [{'case_ids': [case['case_id'] for case in cases],
                             'deliberate_differences': [spec['difference']],
                             'fixed_conditions': ['same authored geometry and public-way assumption',
                                                  'same vehicle blueprint and four cameras',
                                                  'same weather and source acquisition method']}],
            'observations': [{'name': item['name'], 'mandatory': True,
                              'description': item['method']} for item in description['channels']],
            'source_observation_mapping': mapping,
            'sources': [{'path': str(assignment_path.relative_to(ROOT)), 'sha256': sha(assignment_path)},
                        {'path': 'runtime/main-pipeline-v1/SOURCE-MANIFEST.json',
                         'sha256': sha(RUNTIME / 'SOURCE-MANIFEST.json')},
                        {'path': 'skills/worker-preparation/SKILL.md', 'sha256': sha(SKILL)}],
            'existing_evidence': assignment['existing_evidence'],
            'runtime_uncertainties': [spec['gap'], 'Native route, full-body position and four-view pixel visibility unverified',
                                      'No CARLA execution or physical acceptance in this worker']}
    write(folder / 'case-plan.json', plan)
    cameras = [{'width': 1920, 'height': 1080, 'x': -8, 'y': 0, 'z': 35, 'pitch': -80, 'yaw': 0},
               {'width': 1280, 'height': 720, 'x': 2, 'y': 0, 'z': 4, 'pitch': -10, 'yaw': 0},
               {'width': 1280, 'height': 720, 'x': -4, 'y': -8, 'z': 5, 'pitch': -12, 'yaw': 25},
               {'width': 1280, 'height': 720, 'x': 7, 'y': -3, 'z': 8, 'pitch': -35, 'yaw': 90}]
    base = {'law_id': law, 'cell_id': assignment['cell_id'], 'actor': assignment['actor'],
            'mode': mode, 'supported_case_ids': [case['case_id'] for case in cases],
            'source_terms': [t['term'] for t in assignment['source_observation_terms']],
            'required_atoms': ['kin.position', 'kin.heading', 'kin.speed'],
            'authored_test_context': {'public_highway_provenance': 'Synthetic authored assumption, no administrative record',
                                      'public_way_road_ids': [1, 2, 3, 4, 5, 6, 7, 11, 12, 13, 14] if mode == 'crossing_priority' else [1, 2, 3, 4, 13] if mode == 'signal' else [1, 2],
                                      'source_law': law, 'exception_and_authority_status': 'unverified'},
            'public_way_road_ids': [], 'max_ticks': 1600, 'target_speed_mps': 5.0,
            'other_speed_mps': 5.0, 'cameras': cameras,
            'divider': {'opening_x_m': [-12, 12], 'barrier_ranges_x_m': [[-80,-12],[12,80]],
                        'roadway_centers_y_m': [-8,8]},
            'crossing': {'highway_road_ids': [1,5], 'junction_id': 101,
                         'separate_intersection_distance_rule_m': 9.144}}
    def selected(case):
        out = dict(base, case=case, selected_case_id=case['case_id'],
                   route_points=len(route(mode,case)))
        if mode == 'speed':
            out['target_speed_mps'] = case['variable_assignments']['commanded_speed_mps']['value']
        return out
    write(folder / 'config.json', selected(cases[0]))
    source_files = ['runner.py','analyze.py','scene_model.py','scene.xodr','tests/test_package.py']
    def construction(case):
        files = [{'path': name, 'content': (folder / name).read_text(),
                  'source': str((folder / name).relative_to(ROOT))} for name in source_files]
        files.append({'path': 'config.json', 'content': json.dumps(selected(case), indent=2) + '\n'})
        return {'case_id': case['case_id'], 'cell_id': assignment['cell_id'], 'actor': assignment['actor'],
                'entrypoint': 'runner.py', 'recording_description': description,
                'measurement_plan': spec['difference'] + '; original trajectory and sources only',
                'static_checks': ['authored OpenDRIVE and route', 'atom preflight', 'capture channel/frame joins'],
                'termination_rules': ['measured route endpoint or max 1600 recorded ticks'],
                'mechanisms': ['native actor controller and four RGB cameras',
                               'PipelineCapture, FrameMap, write_result, world_restore'],
                'files': files}
    write(folder / 'construction.json', construction(cases[0]))
    entries = []
    for case in cases:
        path = folder / 'constructions' / (case['case_id'] + '.json')
        write(path, construction(case))
        acquisition = {name: {'entrypoint': 'runner.py', 'method': channel(name)['method'],
                              'evidence': ['trace.jsonl', 'capture/evidence.jsonl',
                                           'channels/' + name + '.jsonl']} for name in names}
        entries.append({'case_id': case['case_id'], 'kind': 'capability',
                        'construction': str(path.relative_to(folder)), 'construction_sha256': sha(path),
                        'measurement_procedure': {'entrypoint': 'analyze.py',
                                                  'output_schema': 'partition02-capability-report-v1'},
                        'acquisition': acquisition})
    write(folder / 'execution-manifest.json', {'format': 'worker-execution-manifest-v1',
          'assignment_id': aid, 'runtime_manifest_sha256': sha(RUNTIME / 'SOURCE-MANIFEST.json'),
          'cases': entries})


if __name__ == '__main__':
    for assignment_id in IDS:
        package(assignment_id)
