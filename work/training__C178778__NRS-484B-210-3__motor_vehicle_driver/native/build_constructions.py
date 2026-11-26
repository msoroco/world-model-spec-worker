"""Materialize two exact CPU-authored right-pass constructions and root import files."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'native'
AID = ROOT.name
IDS = {suffix: AID + '__' + suffix for suffix in ('false', 'true')}
CHANNELS = (
    ('right_pass', 'Original ego/lead body overlap and longitudinal order'),
    ('paved_footprint', 'Original ego body corners against paved right edge'),
    ('paved_clearance', 'Measured lead right body edge to paved boundary'),
    ('ego_pose', 'Original Native subject transform and bounding box'),
    ('lead_pose', 'Original Native overtaken vehicle transform and bounding box'),
    ('road_surface', 'Original OpenDRIVE road and shoulder material review'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def recording_description():
    return {'channels': [{'name': name, 'unit': 'structured', 'method': method,
                          'sampling_rate_hz': 20, 'time_window': '600 frames / 30 s',
                          'reference_frame': 'C178778 original Native road and frame',
                          'uncertainty': '50 ms samples; physical material and legal judgment pending'}
                         for name, method in CHANNELS],
            'context_inputs': [{'name': 'four_source_cameras', 'unit': 'video',
                                'method': 'Native camera frame IDs and full source decode'}],
            'limitations': ['Authored lateral clearance is a plan until original Native bodies and surface are reviewed',
                            'No synthetic fixture or controller request establishes a legal verdict']}


def build():
    description = recording_description()
    common_sources = ('runner.py', 'geometry.py', 'necessity.py',
                      'measure_original.py', 'finalize.py', 'tests/test_bundle.py')
    for name in common_sources:
        source = NATIVE / name
        target = ROOT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    for suffix, case_id in IDS.items():
        lead_y, ego_y = (-2.0, -6.0) if suffix == 'false' else (-6.0, -8.7)
        config = {'assignment_id': AID, 'actor': 'motor_vehicle_driver',
                  'law_id': 'NRS-484B-210-3', 'cell_id': 'C178778',
                  'case_id': case_id, 'selected_case_id': case_id,
                  'supported_case_ids': list(IDS.values()), 'candidate_id': 'primary',
                  'case': {'case_id': case_id, 'recording_description': description,
                           'lead_y_plan_m': lead_y, 'ego_y_plan_m': ego_y},
                  'duration_s': 30, 'rate_hz': 20, 'frames': 600,
                  'required_atoms': [], 'source_packets': [],
                  'cameras': [{'name': name, 'width': width, 'height': height,
                               'fov_deg': 85, 'pose_strategy':
                               'ego_attached' if name == 'driver_reference' else 'surveyed_world'}
                              for name, width, height in
                              (('overview', 1920, 1080), ('approach', 1280, 720),
                               ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))],
                  'recording_description': description,
                  'physical_acceptance_claimed': False, 'legal_verdict': None}
        config_path = NATIVE / 'configs' / (suffix + '.json')
        write(config_path, config)
        sources = [(name, NATIVE / name) for name in common_sources]
        sources.append(('config.json', config_path))
        files = [{'path': name, 'source': str(source.relative_to(ROOT.parents[1])),
                  'content': source.read_text()} for name, source in sources]
        construction = {'format': 'worker-construction', 'assignment_id': AID,
                        'case_id': case_id, 'cell_id': 'C178778',
                        'law_id': 'NRS-484B-210-3', 'actor': 'motor_vehicle_driver',
                        'entrypoint': 'runner.py', 'files': files,
                        'recording_description': description,
                        'measurement_plan': {'method': 'source-joined original ego/lead bodies, paved boundary and right-pass timing',
                                             'paved_right_edge_y_m': -8.0,
                                             'lead_y_plan_m': lead_y, 'ego_y_plan_m': ego_y,
                                             'legal_threshold_claimed': False},
                        'mechanisms': ['authored one-way two-paved-lane OpenDRIVE road and shoulder',
                                       'separate ego and overtaken motor-vehicle actors',
                                       'two controlled lateral route alternatives and four synchronized cameras'],
                        'static_checks': ['600 frame / 30 s original source capture',
                                          'two distinct original motor vehicles and road lane readback',
                                          'paved-right clearance math and four source cameras'],
                        'termination_rules': ['abort if original camera frame join differs',
                                              'abort if map route lane is unavailable',
                                              'retain source and restoration seal after 600 frames']}
        write(NATIVE / (suffix + '-construction.json'), construction)
        if suffix == 'false':
            write(ROOT / 'config.json', config)
            write(ROOT / 'construction.json', construction)
    return {'case_ids': list(IDS.values()), 'files_per_construction': len(files)}


if __name__ == '__main__':
    print(json.dumps(build()))
