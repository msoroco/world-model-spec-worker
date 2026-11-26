"""Build immutable City-space case bundles from owned implementation sources."""

import json
from pathlib import Path

from city_space import CASES
from source_packet import ASSIGNMENT

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MODULES = ('runner.py', 'analysis.py', 'city_space.py', 'source_packet.py',
           'native_capture.py', 'physical_completion.py')
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def description():
    descriptions = (
        ('vehicle_status', 'source status', 'authoritative City-vehicle status, distinct from livery'),
        ('space_authority', 'source status', 'Council designation and exact official posting'),
        ('space_occupancy', 'metres', 'original complete footprint against reviewed governed-space bounds'),
        ('parking_motion', 'metres per second', 'original speed and position through parked interval'),
        ('camera_frame_identity', 'Native frame ID', 'four original synchronized camera frame joins'),
    )
    return {'channels': [
        {'name': name, 'unit': unit, 'method': method,
         'sampling_rate_hz': 20, 'time_window': 'all 900 original frames',
         'reference_frame': 'reviewed City street or facility source and original Native frame',
         'uncertainty': 'synthetic fixture and livery do not establish legal status or pixels'}
        for name, unit, method in descriptions],
        'context_inputs': [
            {'name': 'reviewed_city_space_authority', 'unit': 'source hashes',
             'method': 'Council designation, municipal status, official device and NRS scope sources'},
            {'name': 'reviewed_vehicle_and_space_identity', 'unit': 'original IDs and metres',
             'method': 'participant IDs and governed-space boundary source'}],
        'limitations': [
            'City-vehicle statutory scope and NRS definition incorporation stay unresolved.',
            'Actual posting authority, complete body visibility and source equivalence require local review.']}


def write():
    desc = description()
    paths = []
    source_paths = MODULES + ('tests/test_city_space.py',)
    for index, case in enumerate(CASES):
        cid = ASSIGNMENT + '__' + case.name
        for candidate in ('primary', 'fallback1'):
            folder = ROOT if index == 0 and candidate == 'primary' else ROOT / 'cases' / case.name
            folder.mkdir(parents=True, exist_ok=True)
            config = {'assignment_id': ASSIGNMENT, 'law_id': 'LVMC-11-52-340',
                      'cell_id': 'C229439', 'actor': 'vehicle_parker',
                      'selected_case_id': cid,
                      'supported_case_ids': [ASSIGNMENT + '__' + item.name for item in CASES],
                      'rate_hz': 20, 'duration_s': 45, 'frame_count': 900,
                      'required_atoms': [], 'source_packets': [],
                      'candidate_id': candidate,
                      'cameras': [{'name': name, 'width': width, 'height': height,
                                   'pose_strategy': 'reviewed exact City-space device and vehicle footprint',
                                   'fov_deg': 90} for name, width, height in CAMERAS],
                      'case': {'case_id': cid, 'recording_description': desc}}
            config_path = folder / ('config.json' if candidate == 'primary'
                                    else 'fallback1-config.json')
            config_path.write_text(json.dumps(config, indent=2) + '\n')
            files = [{'path': name, 'source': str((ROOT / name).relative_to(REPO)),
                      'content': (ROOT / name).read_text(encoding='utf-8')}
                     for name in source_paths]
            files.append({'path': 'config.json', 'content': config_path.read_text()})
            construction = {'law_id': 'LVMC-11-52-340', 'cell_id': 'C229439',
                            'actor': 'vehicle_parker', 'case_id': cid,
                            'candidate_id': candidate, 'entrypoint': 'runner.py',
                            'diagnostic_only': True,
                            'recording_description': desc, 'files': files,
                            'measurement_plan': 'original 900-frame footprint, authority and parking motion joins',
                            'static_checks': ['Council and fleet source hashes',
                                              'exact device and governed-space source',
                                              'Native actor and four-camera readback'],
                            'termination_rules': ['900 synchronized Native ticks',
                                                  'encoders closed and world restoration verified'],
                            'mechanisms': ['source-gated physical City-space parking',
                                           'complete original participant and camera capture']}
            construction_path = folder / ('construction.json' if candidate == 'primary'
                                          else 'fallback1-construction.json')
            construction_path.write_text(json.dumps(construction, indent=2) + '\n')
            paths.append((cid, candidate, construction_path))
    return paths


if __name__ == '__main__':
    for cid, candidate, path in write():
        print(cid, candidate, path.stat().st_size)
