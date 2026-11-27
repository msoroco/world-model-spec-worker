"""Build immutable service parking case bundles from owned implementation sources."""

import json
from pathlib import Path

from service_parking import CASES
from source_packet import ASSIGNMENT

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MODULES = ('runner.py', 'analysis.py', 'service_parking.py', 'source_packet.py',
           'native_capture.py', 'physical_completion.py')
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def description():
    descriptions = (
        ('commercial_vehicle_dimensions', 'feet and pounds', 'reviewed commercial classification, overall length and independent unladen-weight source'),
        ('street_adjacency_and_frontage', 'feet', 'public street, public school or park adjacency, and residential frontage'),
        ('parking_device_permission', 'source status', 'exact device face and posted-permission authority at governed curb'),
        ('parked_vehicle_footprint', 'metres', 'original complete heavy-vehicle footprint and speed through parked interval'),
        ('worksite_activity_and_distance', 'metres', 'actual service/repair/construction worksite and worker readback relative to parked vehicle'),
        ('loading_and_other_exceptions', 'source status', 'separate expeditious loading and section-wide exception facts'),
        ('camera_frame_identity', 'Native frame ID', 'four original synchronized camera frame joins'),
    )
    return {'channels': [
        {'name': name, 'unit': unit, 'method': method,
         'sampling_rate_hz': 20, 'time_window': 'all 900 original frames',
         'reference_frame': 'reviewed public street, curb and worksite source and original Native frame',
         'uncertainty': 'synthetic fixture does not establish legal status, unladen weight or pixels'}
        for name, unit, method in descriptions],
        'context_inputs': [
            {'name': 'reviewed_service_parking_sources', 'unit': 'source hashes',
             'method': 'independent jurisdiction, street, school or park, vehicle, weight, work order, sign and loading source records'},
            {'name': 'reviewed_vehicle_work_identity', 'unit': 'original IDs and metres',
             'method': 'vehicle, driver, worker, worksite and curb identities and coordinates'}],
        'limitations': [
            'Modifier scope, residence district classification, immediate neighborhood and similar essential use remain legal judgments.',
            'Actual unladen weight, work activity, exact sign permission and complete body pixels require independent source review.']}


def write():
    desc = description()
    paths = []
    source_paths = MODULES + ('tests/test_service_parking.py',)
    for index, case in enumerate(CASES):
        cid = ASSIGNMENT + '__' + case.name
        for candidate in ('primary', 'fallback1'):
            folder = ROOT if index == 0 and candidate == 'primary' else ROOT / 'cases' / case.name
            folder.mkdir(parents=True, exist_ok=True)
            config = {'assignment_id': ASSIGNMENT, 'law_id': 'LVMC-11-52-305-A',
                      'cell_id': 'C229439', 'actor': 'heavy_vehicle_driver',
                      'selected_case_id': cid,
                      'supported_case_ids': [ASSIGNMENT + '__' + item.name for item in CASES],
                      'rate_hz': 20, 'duration_s': 45, 'frame_count': 900,
                      'required_atoms': [], 'source_packets': [],
                      'candidate_id': candidate,
                      'cameras': [{'name': name, 'width': width, 'height': height,
                                   'pose_strategy': 'reviewed heavy vehicle, curb, sign, worksite and worker',
                                   'fov_deg': 90} for name, width, height in CAMERAS],
                      'case': {'case_id': cid, 'recording_description': desc}}
            config_path = folder / ('config.json' if candidate == 'primary'
                                    else 'fallback1-config.json')
            config_path.write_text(json.dumps(config, indent=2) + '\n')
            files = [{'path': name, 'source': str((ROOT / name).relative_to(REPO)),
                      'content': (ROOT / name).read_text(encoding='utf-8')}
                     for name in source_paths]
            files.append({'path': 'config.json', 'content': config_path.read_text()})
            construction = {'law_id': 'LVMC-11-52-305-A', 'cell_id': 'C229439',
                            'actor': 'heavy_vehicle_driver', 'case_id': cid,
                            'candidate_id': candidate, 'entrypoint': 'runner.py',
                            'diagnostic_only': True,
                            'recording_description': desc, 'files': files,
                            'measurement_plan': 'original 900-frame heavy footprint, sourced dimensions, adjacency and actual worksite joins',
                            'static_checks': ['public school or park, residence frontage and vehicle authority hashes',
                                              'exact device, work order and governed-curb sources',
                                              'Native actor and four-camera readback'],
                            'termination_rules': ['900 synchronized Native ticks',
                                                  'encoders closed and world restoration verified'],
                            'mechanisms': ['source-gated heavy vehicle parking and actual worksite/worker activity',
                                           'complete original participant and camera capture']}
            construction_path = folder / ('construction.json' if candidate == 'primary'
                                          else 'fallback1-construction.json')
            construction_path.write_text(json.dumps(construction, indent=2) + '\n')
            paths.append((cid, candidate, construction_path))
    return paths


if __name__ == '__main__':
    for cid, candidate, path in write():
        print(cid, candidate, path.stat().st_size)
