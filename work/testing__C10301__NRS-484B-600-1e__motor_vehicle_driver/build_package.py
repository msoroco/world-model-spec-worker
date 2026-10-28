"""Freeze three exact 80 mph capability cases from this assignment's supplied input."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
INPUT = REPO / 'inputs' / AID / 'assignment.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    assignment = json.loads(INPUT.read_text())
    runtime = REPO / 'runtime/main-pipeline-v1'
    description = {'channels': [
        {'name': 'kin.speed', 'unit': 'm/s', 'sampling_rate_hz': 20,
         'method': 'original actor velocity norm each recorded tick',
         'time_window': 'entire original run', 'reference_frame': 'CARLA world',
         'uncertainty': '20 Hz source sample and CARLA velocity telemetry'},
        {'name': 'kin.velocity', 'unit': 'm/s', 'sampling_rate_hz': 20,
         'method': 'original actor native XYZ velocity vector each recorded tick',
         'time_window': 'entire original run', 'reference_frame': 'CARLA world',
         'uncertainty': '20 Hz source sample and CARLA velocity telemetry'},
        {'name': 'kin.position', 'unit': 'm', 'sampling_rate_hz': 20,
         'method': 'original actor native XYZ position each recorded tick',
         'time_window': 'entire original run', 'reference_frame': 'CARLA world',
         'uncertainty': '20 Hz source sample and CARLA transform telemetry'},
        {'name': 'ru.subject', 'unit': 'structured record', 'sampling_rate_hz': 20,
         'method': 'original actor ID, blueprint, and subject role at each recorded tick',
         'time_window': 'entire original run', 'reference_frame': 'native actor inventory',
         'uncertainty': 'synthetic subject attribution must be checked at live capture'}],
        'context_inputs': [],
        'limitations': ['Synthetic public vehicular access is an authored setup assumption.',
                        'Diagnostic fixtures are incomplete motion and cannot prove an 80 mph crossing.']}
    cases = []
    for label, mph in [('below_80', 79), ('at_80', 80), ('above_80', 81)]:
        cases.append({'case_id': AID + '__' + label, 'target_law_id': assignment['law_id'],
            'target_type': 'boundary_probe',
            'rationale': 'Freeze an exact commanded speed near the stated absolute 80 mph number; measure original maximum without assigning a legal verdict.',
            'variable_assignments': {'commanded_speed_mps': {'value': mph * .44704,
                                      'unit': 'm/s', 'kind': 'controller'}},
            'unresolved_judgment_calls': ['synthetic public highway status',
                                          'actual achievable speed and transient response'],
            'recording_description': description})
    write(ROOT / 'proposals/cases.json', {'status': 'draft', 'cell_id': assignment['cell_id'],
         'actor': assignment['actor'], 'sweep_specs': [], 'cases': cases})
    mapping = {
        'kin.speed': {'evidence': 'Original full-trace velocity norm, including the maximum and first frame above the statutory numeric boundary.',
                      'channels': ['kin.speed'], 'source_refs': ['trace.jsonl']},
        'kin.velocity': {'evidence': 'Original native XYZ velocity vector used to check scalar speed provenance.',
                         'channels': ['kin.velocity'], 'source_refs': ['trace.jsonl']},
        'ru.subject': {'evidence': 'Original CARLA actor ID and blueprint identify the measured subject vehicle.',
                       'channels': ['ru.subject'], 'source_refs': ['capture/evidence.jsonl']}}
    plan = {'assignment_id': AID, 'actor': assignment['actor'],
        'cell_id': assignment['cell_id'], 'law_id': assignment['law_id'],
        'cases': cases,
        'comparisons': [{'case_ids': [case['case_id'] for case in cases],
                         'deliberate_differences': ['commanded speed: 79, 80, 81 mph'],
                         'fixed_conditions': ['same authored highway/access corridor',
                                              'same motor vehicle, camera and controller configuration']}],
        'observations': [{'name': c['name'], 'mandatory': True,
                          'description': c['method']} for c in description['channels']],
        'source_observation_mapping': mapping,
        'sources': [{'path': str(INPUT.relative_to(REPO)), 'sha256': sha(INPUT)},
                    {'path': 'runtime/main-pipeline-v1/SOURCE-MANIFEST.json',
                     'sha256': sha(runtime / 'SOURCE-MANIFEST.json')},
                    {'path': 'skills/worker-preparation/SKILL.md',
                     'sha256': sha(REPO / 'skills/worker-preparation/SKILL.md')}],
        'existing_evidence': assignment['existing_evidence'],
        'runtime_uncertainties': ['native speed capability and duration',
            'achieved roadway position', 'synthetic public-highway context',
            'four-view camera visibility and final physical cause']}
    write(ROOT / 'case-plan.json', plan)
    base = {'law_id': assignment['law_id'], 'cell_id': assignment['cell_id'],
        'actor': assignment['actor'], 'supported_case_ids': [c['case_id'] for c in cases],
        'required_atoms': ['kin.speed', 'kin.velocity', 'kin.position', 'ru.subject'],
        'authored_test_context': {'public_way_road_ids': [1],
            'public_vehicular_access': 'synthetic authored assumption, not observed jurisdictional fact',
            'layout': '650 m undivided two-way access corridor'},
        'controller': {'speed_kp': .2},
        'max_ticks': 600,
        'cameras': [{'width': 1920, 'height': 1080, 'x': -8, 'y': 0, 'z': 30,
                     'pitch': -78, 'yaw': 0},
                    {'width': 1280, 'height': 720, 'x': 2, 'y': 0, 'z': 4,
                     'pitch': -10, 'yaw': 0},
                    {'width': 1280, 'height': 720, 'x': -4, 'y': -6, 'z': 5,
                     'pitch': -15, 'yaw': 25},
                    {'width': 1280, 'height': 720, 'x': 7, 'y': -2, 'z': 7,
                     'pitch': -32, 'yaw': 90}]}
    common = ['runner.py', 'analyze.py', 'scene.xodr', 'tests/test_speed.py']

    def construction(case):
        selected = dict(base, case=case, selected_case_id=case['case_id'])
        files = [{'path': path, 'content': (ROOT / path).read_text(),
                  'source': str((ROOT / path).relative_to(REPO))} for path in common]
        files.append({'path': 'config.json', 'content': json.dumps(selected, indent=2) + '\n'})
        return {'case_id': case['case_id'], 'cell_id': assignment['cell_id'],
            'actor': assignment['actor'], 'entrypoint': 'runner.py',
            'recording_description': description,
            'measurement_plan': 'Full original speed and velocity history, maximum and first 80 mph exceedance bracket; no legal verdict.',
            'static_checks': ['OpenDRIVE road and lane geometry', 'native four-camera sizes',
                              'original frame and channel join'],
            'termination_rules': ['measured x>=520 m endpoint and slowdown or 600 ticks'],
            'mechanisms': ['native vehicle control', 'PipelineCapture', 'FrameMap',
                           'four lossless RGB source videos', 'world restoration'],
            'files': files}

    write(ROOT / 'config.json', dict(base, case=cases[0], selected_case_id=cases[0]['case_id']))
    write(ROOT / 'construction.json', construction(cases[0]))
    entries = []
    for case in cases:
        path = ROOT / 'constructions' / (case['case_id'] + '.json')
        write(path, construction(case))
        acquisition = {name: {'entrypoint': 'runner.py',
            'method': 'same-frame native actor state through PipelineCapture and original actor inventory',
            'evidence': ['trace.jsonl', 'capture/evidence.jsonl', 'channels/' + name + '.jsonl']}
            for name in base['required_atoms']}
        entries.append({'case_id': case['case_id'], 'kind': 'capability',
            'construction': str(path.relative_to(ROOT)), 'construction_sha256': sha(path),
            'measurement_procedure': {'entrypoint': 'analyze.py',
                                      'output_schema': 'absolute-speed-capability-v1'},
            'acquisition': acquisition})
    write(ROOT / 'execution-manifest.json', {'format': 'worker-execution-manifest-v1',
        'assignment_id': AID, 'runtime_manifest_sha256': sha(runtime / 'SOURCE-MANIFEST.json'),
        'cases': entries})


if __name__ == '__main__':
    main()
