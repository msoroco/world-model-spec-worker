"""Build source-bound inline constructions for two selected worker encounters."""

from __future__ import annotations

import json
from pathlib import Path

import runner
from native.person_scene import MODES

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
CHANNELS = ('drv.time_to_conflict', 'drv.hard_deceleration', 'kin.speed',
            'kin.accel_longitudinal', 'kin.yaw_rate', 'rel.surface_gap',
            'rel.contact', 'st.highway', 'ru.pedestrian')
SOURCE_FILES = ('runner.py', 'finalize.py', 'native/person_scene.py',
                'native/person_interaction.py', 'tests/test_selected.py')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def main():
    recording = {
        'channels': [{'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                      'method': 'original Native ego and distinct roadside-worker pose, velocity, acceleration, collision and context source joined by frame',
                      'time_window': 'complete 600-frame, 30-second encounter',
                      'reference_frame': 'authored paved-road coordinates and original Native frame',
                      'uncertainty': 'Highway/access legal status, worker role, sight lines, weather and willful or wanton mental state require independent source review'}
                     for name in CHANNELS],
        'context_inputs': [],
        'limitations': [
            'Synthetic CPU samples do not establish original highway dedication or public access.',
            'A roadside worker identity and role require original scene and independent review.',
            'No telemetry surrogate or threshold establishes willful or wanton disregard.']}
    for suffix, mode in MODES.items():
      for candidate_id, worker_y in (('primary', -5.2), ('fallback1', -4.8)):
        directory = HERE / 'cases' / suffix
        case_id = runner.CASE_PREFIX + suffix
        config = {
            'actor': 'motor_vehicle_driver', 'law_id': 'NRS-484B-653-1a',
            'cell_id': 'C179799', 'case_id': case_id,
            'selected_case_id': case_id, 'case_suffix': suffix,
            'case': {'case_id': case_id, 'recording_description': recording},
            'candidate_id': candidate_id, 'interaction_mode': mode,
            'worker_y_m': worker_y,
            'duration_s': 30, 'duration_frames': 600, 'rate_hz': 20,
            'cameras': [{'name': name, 'width': width, 'height': height,
                         'fov_deg': 85, 'fps': 20,
                         'pose_strategy': 'vehicle-attached original Native mount in runner.py'}
                        for name, width, height, *_ in runner.CAMERAS],
            'required_atoms': ['kin.position', 'kin.speed'],
            'source_packets': [], 'mandatory_channels': list(CHANNELS),
            'recording_description': recording,
            'authored_test_context': {'core_assumptions': []},
            'public_way_road_ids': [],
            'requested_speed_mps': 8.0,
            'physical_completion': {'criterion': 'travel_progress',
                                    'motion_source': 'trace.jsonl',
                                    'position_key': 'position_m',
                                    'minimum_progress_m': 35.0},
            'physical_verified': False, 'legal_verdict': None,
            'status': 'prospective_original_native_capture'}
        config_path = directory / ('config.json' if candidate_id == 'primary' else 'config-fallback1.json')
        write(config_path, config)
        files = [{'path': name, 'content': (HERE / name).read_text()}
                 for name in SOURCE_FILES]
        files.append({'path': 'config.json', 'content': config_path.read_text()})
        construction = {
            'format': 'worker-inline-construction', 'case_id': case_id,
            'candidate_id': candidate_id, 'law_id': config['law_id'],
            'cell_id': config['cell_id'], 'actor': config['actor'],
            'entrypoint': 'runner.py', 'files': files,
            'recording_description': recording,
            'measurement_plan': {
                'entrypoint': 'finalize.py',
                'required_sources': ['native-person-interaction.jsonl',
                                     'original-context-packet.json',
                                     'native-road-readback.json',
                                     'video_frames.jsonl', 'trace.jsonl',
                                     'capture/evidence.jsonl'],
                'source_review_required': True},
            'static_checks': [
                'One authored paved road, surveyed Native driving lane and distinct walker actor',
                '600 frame, 20 Hz original Native actor, collision sensor and four-camera joins',
                'Exact original context packet required; highway/public access not inferred from OpenDRIVE'],
            'mechanisms': [
                'Conventional vehicle is spawned on authored paved lane; distinct roadside worker is spawned outside the right lane edge',
                'Earlier and later response settings vary only engineering brake onset distance',
                'Original actor positions, velocities, acceleration, yaw, collision events, four camera pixels, and contextual sources retained'],
            'termination_rules': [
                '600 original Native frames or explicit failure',
                'Close encoders and Native recorder, destroy owned actors and restore exclusive world'],
            'status': 'cpu_construction_physical_unverified'}
        write(directory / ('construction.json' if candidate_id == 'primary' else 'construction-fallback1.json'), construction)
        if suffix == 'condition_a' and candidate_id == 'primary':
            write(HERE / 'config.json', config)
            write(HERE / 'construction.json', construction)
    print(json.dumps({'case_ids': [runner.CASE_PREFIX + x for x in MODES]}))


if __name__ == '__main__':
    main()
