"""Validate the attention case stage without inventing an attention finding."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path


FOLDER = Path(__file__).resolve().parents[1]
REPO = FOLDER.parents[1]
PROPOSALS = FOLDER / 'proposals'


def read(name):
    return json.loads((PROPOSALS / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    from batch_pipeline import stages

    assignment = json.loads((REPO / 'inputs' / FOLDER.name / 'assignment.json').read_text())
    template = read('template.json')
    binding = read('bindings.json')
    judgment = read('judgment-observables-1.json')
    phrase = template['structure']['judgment_calls_needed'][0]
    assert (judgment['phrase'], judgment['note']) == (phrase['phrase'], phrase['note'])
    record = {
        'channels': [
            {'name': 'ego_pose', 'unit': 'structured', 'sampling_rate_hz': 20,
             'method': 'original frame-joined Native motion', 'time_window': 'full 30 s',
             'reference_frame': 'world', 'uncertainty': 'source frame and pose fidelity'},
            {'name': 'ego_speed', 'unit': 'm/s', 'sampling_rate_hz': 20,
             'method': 'original frame-joined Native motion', 'time_window': 'full 30 s',
             'reference_frame': 'ego', 'uncertainty': 'source velocity fidelity'},
            {'name': 'driver_reference_video', 'unit': 'video', 'sampling_rate_hz': 20,
             'method': 'synchronized original source camera', 'time_window': 'full 30 s',
             'reference_frame': 'camera', 'uncertainty': 'driver visibility and sufficiency need review'},
        ],
        'context_inputs': [
            {'name': 'driver_attention_source_review', 'unit': 'structured',
             'method': 'independent review of original operator and scene evidence; pending'},
            {'name': 'native_driving_context', 'unit': 'structured',
             'method': 'source-hashed vehicle, route, camera pose and timing; pending'},
        ],
        'limitations': [
            'A scripted simulator vehicle and synthetic camera pixels cannot establish a person\'s attention.',
            'The driver and scene review is unperformed; no legal finding is made.',
        ],
    }
    assignments = {
        'driver_attention_to_operation': {'kind': 'subject_behavior', 'value': None},
        'vehicle_operation_context': {'kind': 'world_setup', 'value': None},
    }
    cases = {
        'cell_id': assignment['cell_id'], 'actor': assignment['actor'], 'status': 'draft',
        'cases': [{
            'case_id': FOLDER.name + '__baseline', 'target_law_id': None,
            'target_type': 'baseline',
            'rationale': 'Shared operation context anchor only; direct attention evidence is pending.',
            'variable_assignments': assignments,
            'recording_description': record,
            'unresolved_judgment_calls': [phrase['phrase']],
        }],
        'sweep_specs': [{
            'sweep_id': 'attention-source-review',
            'target_law_id': assignment['law_id'],
            'judgment_refs': [phrase], 'status': 'incomplete',
            'rationale': 'A driver-attention axis cannot be chosen from vehicle motion or an unreviewed camera.',
            'missing_inputs': [
                'Original operator-facing evidence tied to the Native vehicle-operation interval',
                'Independent visibility and attention review before choosing physical coverage axes',
            ],
        }],
    }
    request = {'cell': assignment['cell'], 'actor': assignment['actor']}
    inputs = {'request': request, 'dependencies': [binding], 'templates': [template]}
    stages.validate('cases', deepcopy(cases), inputs)
    checks = {}
    for name, mutation, expected in (
        ('missing_sweep', lambda value: value.update(sweep_specs=[]),
         'Missing judgment sweep plan'),
        ('invented_attention', lambda value: value['cases'][0]['variable_assignments'][
            'driver_attention_to_operation'].update(value='attentive'),
         'Incorrect variable kind or guaranteed behavior'),
        ('missing_recorded_channels', lambda value: value['cases'][0]['recording_description'][
            'channels'].clear(), 'Recording description needs channels/context/limitations'),
    ):
        bad = deepcopy(cases)
        mutation(bad)
        try:
            stages.validate('cases', bad, inputs)
        except ValueError as error:
            if expected not in str(error):
                raise
            checks[name] = str(error)
        else:
            raise ValueError('Invalid case stage passed: ' + name)
    path = PROPOSALS / 'cases-foundation.json'
    path.write_text(json.dumps(cases, indent=2) + '\n')
    proof = {
        'format': 'c230222-cases-foundation-cpu-v1', 'passed': True,
        'case_stage_sha256': sha(path), 'case_stage_path': 'proposals/cases-foundation.json',
        'baseline_count': 1, 'incomplete_judgment_sweep_count': 1,
        'negative_rejections': checks, 'delivery_selected': False,
        'driver_attention_observed': False,
    }
    proof_path = PROPOSALS / 'cases-foundation-proof.json'
    proof_path.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed': True, 'negative_rejections': len(checks),
                      'proof_sha256': sha(proof_path)}))


if __name__ == '__main__':
    main()
