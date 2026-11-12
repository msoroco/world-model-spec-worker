"""Materialize the first selected C228670 Native construction for offline checks."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__approach_near_depart_right'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


recording = {
    'channels': [
        {'name': 'approach_left_curb_distance_m', 'unit': 'm',
         'method': 'original four-corner body position relative to one-way source left curb',
         'sampling_rate_hz': 20, 'time_window': 'approach frames',
         'reference_frame': 'Native map ground plane',
         'uncertainty': 'lane-edge map geometry and sampled body corners'},
        {'name': 'departure_centerline_signed_m', 'unit': 'm',
         'method': 'original four-corner body position relative to entered road directed centerline',
         'sampling_rate_hz': 20, 'time_window': 'leaving-intersection frames',
         'reference_frame': 'Native map ground plane',
         'uncertainty': 'road-center map geometry and sampled body corners'},
    ],
    'context_inputs': [
        {'name': 'road_geometry', 'unit': 'structured record',
         'method': 'original OpenDRIVE lane directionality and map curb/centerline readback'},
        {'name': 'body_footprints', 'unit': 'structured record',
         'method': 'original joined subject ground-body corners and approach/departure phases'},
    ],
    'limitations': ['Practicability and actual right-of-centerline visibility require independent physical/legal review.'],
}
config = {
    'law_id': 'NRS-484B-400-4', 'cell_id': 'C228670', 'actor': 'motor_vehicle_driver',
    'selected_case_id': CASE,
    'supported_case_ids': [ROOT.name + '__' + slug for slug in (
        'approach_near_depart_right', 'approach_far_depart_right', 'approach_near_depart_left')],
    'required_atoms': [], 'source_packets': [],
    'rate_hz': 20, 'duration_s': 8, 'frames': 160, 'route_step_m': 2.0,
    'cameras': [
        {'name': name, 'width': width, 'height': height,
         'pose_strategy': 'subject-mounted original turn, curb and entered-road view', 'fov_deg': fov}
        for name, width, height, fov in (
            ('overview', 1920, 1080, 95), ('approach', 1280, 720, 90),
            ('reference_corner', 1280, 720, 100), ('driver_reference', 1280, 720, 85))],
    'case': {'case_id': CASE, 'recording_description': recording},
    'physical_completion': {'criterion': 'left_turn_entry_and_departure',
        'motion_source': 'body_footprints.jsonl', 'position_key': 'ground_corners',
        'context_sources': ['road_geometry.json']},
}
(ROOT / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
files = []
for relative in ('runner.py', 'turn_native_runner.py', 'turn_camera_capture.py',
                 'turn_geometry.py', 'turn_comparison_audit.py', 'turn_finalizer.py', 'config.json',
                 'tests/test_turn_geometry.py', 'tests/test_turn_native_runner.py',
                 'tests/test_turn_finalizer.py'):
    source = ROOT / relative
    files.append({'path': relative, 'content': source.read_text(),
                  'source': str(source.relative_to(REPO))})
construction = {
    'format': 'worker-construction', 'case_id': CASE,
    'cell_id': 'C228670', 'law_id': 'NRS-484B-400-4', 'actor': 'motor_vehicle_driver',
    'entrypoint': 'runner.py', 'files': files,
    'measurement_plan': [
        'original one-way and two-directional lane geometry with source left curb and destination centerline',
        'original approach and leaving-intersection four-corner body footprints',
        'independent approach-curb and departure-centerline comparisons without legal practicability cutoff'],
    'recording_description': recording,
    'static_checks': ['connected one-way-to-two-way left-turn route and junction',
                      'source/destination lane directionality and original map lines',
                      'four synchronized original cameras and subject ground-body corners'],
    'termination_rules': ['160 original 20 Hz Native frames or explicit failure'],
    'mechanisms': ['route pursuit controller through left-turn junction',
                   'commanded approach curb offset and departure centerline side'],
}
source = ROOT / 'construction.json'
source.write_text(json.dumps(construction, indent=2) + '\n')
manifest = {'format': 'worker-compatibility-manifest', 'assignment_id': ROOT.name,
            'runtime_manifest_sha256': json.loads((REPO / 'batch.json').read_text())['runtime']['source_manifest_sha256'],
            'cases': [{'case_id': CASE, 'construction': 'construction.json',
                       'construction_sha256': sha(source), 'kind': 'delivery'}]}
(ROOT / 'construction-probe-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('Materialized first exact C228670 Native construction')
