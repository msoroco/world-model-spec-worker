"""Build the first exact flashing-yellow inline construction for CPU proof."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
repo = root.parents[1]
assignment = root.name
case_id = assignment + '__east_cautious_approach'
from signal_camera_capture import CAMERAS

description = {'channels': [
    {'name': name, 'unit': unit, 'method': method,
     'sampling_rate_hz': 20, 'time_window': 'all original frames',
     'reference_frame': 'Native world and original frame identity',
     'uncertainty': 'Native state does not establish visual appearance or legal caution'}
    for name, unit, method in (
        ('native_yellow_on', 'boolean', 'saved Native light state readback'),
        ('ego_speed_mps', 'm/s', 'saved ego velocity magnitude'),
        ('ego_center_xy', 'm', 'saved ego world center'),
        ('crossing_center_xy', 'm', 'saved crossing vehicle world center'))],
    'context_inputs': [],
    'limitations': ['Official status, lens illumination in pixels, and caution require independent source review.']}
config = {
    'cell_id': 'C111273', 'law_id': 'NRS-484B-310-2',
    'actor': 'motor_vehicle_driver', 'selected_case_id': case_id,
    'supported_case_ids': [assignment + '__' + branch for branch in (
        'east_cautious_approach', 'east_faster_approach',
        'east_clear_approach', 'west_cautious_approach')],
    'case_branch': 'east_cautious_approach',
    'official_control_source': 'Native traffic-light actor and governed OpenDRIVE lane; official status requires independent review',
    'flash_period_s': .5, 'target_speed_mps': 4.0,
    'required_atoms': [], 'source_packets': [],
    'rate_hz': 20, 'duration_s': 8, 'frames': 160,
    'cameras': [{'name': name, 'width': spec[2][0], 'height': spec[2][1],
                 'pose_strategy': 'subject-mounted original RGB source',
                 'fov_deg': spec[3]} for name, spec in CAMERAS.items()],
    'case': {'case_id': case_id, 'recording_description': description}}
(root/'config.json').write_text(json.dumps(config, indent=2)+'\n')
paths = ['runner.py', 'native_signal.py', 'flashing_yellow.py',
         'signal_camera_capture.py', 'signal_capture_session.py',
         'signal_finalizer.py', 'signal_comparison_audit.py', 'config.json',
         'tests/test_runner.py', 'tests/test_native_signal.py',
         'tests/test_flashing_yellow.py', 'tests/test_signal_finalizer.py']
files = [{'path': path, 'source': str((root/path).relative_to(repo)),
          'content': (root/path).read_text()} for path in paths]
construction = {'format': 'worker-inline-construction', 'case_id': case_id,
    'cell_id': 'C111273', 'law_id': 'NRS-484B-310-2',
    'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py', 'files': files,
    'measurement_plan': {'finalizer': 'signal_finalizer.py',
        'retained_sources': ['signal_context.json', 'signal_state.jsonl',
            'participant_state.jsonl', 'video_frames.jsonl', 'trace.jsonl'],
        'reported_boundary': 'Native yellow/off transitions and approach motion; lens pixels, authority and caution unresolved'},
    'recording_description': description,
    'static_checks': ['runner --check', 'source-shaped Native and finalizer CPU tests'],
    'termination_rules': ['160 original 20 Hz frames', 'reject missing signal or participant frame'],
    'mechanisms': ['Native governed light and two approach lanes',
        'crossing actor', 'four original RGB sources', 'saved-only signal finalizer']}
(root/'construction.json').write_text(json.dumps(construction, indent=2)+'\n')
digest = hashlib.sha256((root/'construction.json').read_bytes()).hexdigest()
manifest = {'format': 'worker-execution-manifest', 'assignment_id': assignment,
    'runtime_manifest_sha256': hashlib.sha256((repo/'runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest(),
    'cases': [{'case_id': case_id, 'kind': 'delivery',
        'construction': 'construction.json', 'construction_sha256': digest,
        'measurement_procedure': {'entrypoint': 'signal_finalizer.py'},
        'candidate_risk': {'status': 'physical', 'reason': 'Native signal appearance and crossing geometry may fail physical capture'},
        'candidates': [],
        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                           'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}}]}
(root/'execution-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
print(digest)
