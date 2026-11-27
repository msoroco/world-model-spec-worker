"""Build exact selected Native source bundles without executing CARLA."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
SUFFIXES = ('stop_early', 'stop_late', 'probe_1', 'probe_2')
TERMS = ('drv.stopped', 'drv.hard_deceleration', 'kin.accel_longitudinal',
         'sig.brake_lamp', 'sig.hand_signal', 'drv.following',
         'rel.ahead_behind_in_lane', 'rel.surface_gap')
CAMERAS = [
    {'name': 'overview', 'width': 1920, 'height': 1080,
     'pose_strategy': 'entire paved route and both actors', 'fov_deg': 85},
    {'name': 'approach', 'width': 1280, 'height': 720,
     'pose_strategy': 'rear-to-ego approach and gap', 'fov_deg': 85},
    {'name': 'reference_corner', 'width': 1280, 'height': 720,
     'pose_strategy': 'ego lamp and stopping region', 'fov_deg': 85},
    {'name': 'driver_reference', 'width': 1280, 'height': 720,
     'pose_strategy': 'ego, rear and road identity', 'fov_deg': 85},
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    description = {
        'channels': [{'name': term, 'unit': 'structured', 'sampling_rate_hz': 20,
                      'method': 'same-tick original Native ego/rear state and observed signal',
                      'time_window': '600 frames', 'reference_frame': 'original Native time and road lane',
                      'uncertainty': 'Signal appropriateness, suddenness and immediate rear are reviewed separately'}
                     for term in TERMS],
        'context_inputs': [{'name': 'rear_signal_context', 'unit': 'structured',
                            'method': 'original highway and signaling source review'}],
        'limitations': ['Synthetic CPU frames establish software compatibility only',
                        'No statutory numeric lead time or suddenness cutoff is supplied'],
    }
    entries = []
    for suffix in SUFFIXES:
        case_id = ASSIGNMENT + '__' + suffix
        action = 'stop' if suffix.startswith('stop') else 'sudden_decrease'
        early = suffix in ('stop_early', 'probe_1')
        config = {
            'case_id': case_id, 'selected_case_id': case_id, 'case': {'case_id': case_id},
            'case_suffix': suffix, 'cell_id': 'C230259', 'law_id': 'NRS-484B-413-3',
            'actor': 'motor_vehicle_driver', 'duration_s': 30, 'rate_hz': 20,
            'frames': 600, 'cameras': CAMERAS, 'required_atoms': [], 'source_packets': [],
            'supported_case_ids': [ASSIGNMENT + '__' + item for item in SUFFIXES],
            'recording_description': description, 'action_kind': action,
            'action_frame': 120,
            'signal_command_frame': 100 if early else 160 if action == 'stop' else 121,
            'rear_gap_requested_m': 12.0, 'diagnostic_deceleration_mps2': 3.0,
            'diagnostic_bound_is_statutory': False,
            'target': f'{action} with signal ' + ('before' if early else 'after') + ' action',
        }
        files = [{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'}]
        for name in ('layout.py', 'runner.py', 'measure_timing.py',
                     'finalize_timing.py', 'tests/test_native.py'):
            files.append({'path': name, 'content': (HERE / name).read_text()})
        for name in ('assignment.json', 'witnesses.json'):
            source = ROOT / 'inputs' / ASSIGNMENT / name
            if source.is_file():
                files.append({'path': name, 'content': source.read_text()})
        proposal = {
            'case_id': case_id, 'cell_id': 'C230259', 'law_id': 'NRS-484B-413-3',
            'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
            'files': files, 'recording_description': description,
            'measurement_plan': {
                'method': '600 same-tick original ego/rear, observed lamp, kinematics and four cameras',
                'output': 'source-hashed action, signal and rear-recipient measurements',
                'legal_cutoff_defined': False},
            'termination_rules': ['600 original frames and synchronized four-camera source',
                                  'close encoders and restore world before sealing'],
            'mechanisms': ['authored 300 m paved shared lane',
                           'two original Native actors with same target-speed profile',
                           'ego lamp command at 100, 121 or 160; action request at 120',
                           'stop versus decrease target-speed profile',
                           'same-tick observed lamp/kinematic/rear source and PipelineCapture'],
            'status': 'selected_native_cpu_draft_not_delivery_prepared',
            'static_checks': ['frozen law and cell', 'shared paved lane and rear actor',
                              'four synchronized FFV1 cameras', '600 frames at 20 Hz',
                              'source-bound signal and action ordering'],
        }
        path = HERE / 'native' / 'bundles' / suffix / 'construction.json'
        write(path, proposal)
        entries.append({'case_id': case_id, 'kind': 'delivery',
                        'construction': str(path.relative_to(HERE)),
                        'construction_sha256': sha(path),
                        'candidate_risk': {'status': 'none', 'reason':
                            'No original Native signal, gap or motion failure has been measured; preserve primary pending first capture'},
                        'candidates': [], 'delivery_readiness': 'incomplete'})
        if suffix == 'stop_early':
            write(HERE / 'config.json', config)
            write(HERE / 'construction.json', proposal)
    write(HERE / 'selected-draft-manifest.json',
          {'format': 'worker-selected-cpu-draft-manifest-v1',
           'assignment_id': ASSIGNMENT, 'status': 'partial', 'cases': entries,
           'physical_acceptance_claimed': False})
    return entries


if __name__ == '__main__':
    print(json.dumps({'constructions': [x['construction_sha256'] for x in build()]}))
