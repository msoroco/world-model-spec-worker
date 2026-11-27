"""Materialize the eight exact parking constructions with source-bound code bytes."""
from __future__ import annotations

import json
from pathlib import Path

from parking import CASES

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
LAW = 'NRS-484B-450-1l'
FILES = ('runner.py', 'native_parking.py', 'site_review.py', 'parking.py',
         'analysis.py', 'case-plan.json', 'tests/test_parking.py')
CAMERAS = [
    {'name': name, 'width': width, 'height': height,
     'pose_strategy': strategy, 'fov_deg': 90}
    for name, width, height, strategy in (
        ('overview', 1920, 1080, 'fixed narrow highway and both vehicles'),
        ('approach', 1280, 720, 'fixed ego approach and edge vehicle'),
        ('reference_corner', 1280, 720, 'fixed curb edge and two vehicle bodies'),
        ('driver_reference', 1280, 720, 'ego mounted highway-side view'))]
CHANNELS = ('site_source', 'edge_reference', 'ego_body_history',
            'edge_vehicle_body_history', 'ego_motion_history',
            'edge_motion_history', 'halt_activity_history',
            'exception_context', 'camera_frame_map')
CONTEXT = ('highway_status', 'driver_identity', 'motor_vehicle_class',
           'edge_vehicle_stopped_or_parked', 'traffic_conflict_necessity',
           'law_compliance', 'police_direction', 'official_device_direction')


def recording():
    return {
        'channels': [
            {'name': name, 'unit': 'structured record', 'sampling_rate_hz': 20,
             'method': 'Original Native frame acquisition and saved-only extraction',
             'time_window': 'narrow highway approach through terminal halt',
             'reference_frame': 'original CARLA world frame and timestamp',
             'uncertainty': '20 Hz sampling and actor bounding-box geometry'}
            for name in CHANNELS],
        'context_inputs': [
            {'name': name, 'unit': 'reviewed source packet',
             'method': 'Reviewed original highway, edge and authority source binding'}
            for name in CONTEXT],
        'limitations': [
            'Geometry alone does not establish a legally qualifying highway or curb.',
            'Stop, stand, park, traffic necessity and authority are independent review questions.',
            'Physical pixels and legal applicability require independent original review.']}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def main():
    all_ids = [AID + '__' + case.case_id for case in CASES]
    description = recording()
    for index, case in enumerate(CASES):
        case_id = all_ids[index]
        config = {
            'assignment_id': AID, 'selected_case_id': case_id,
            'supported_case_ids': all_ids, 'law_id': LAW,
            'cell_id': 'C135705', 'actor': 'motor_vehicle_driver',
            'rate_hz': 20, 'duration_s': 45,
            'engineering_throttle': 0.25,
            'engineering_braking_factor': 5.0,
            'required_atoms': [], 'source_packets': [], 'cameras': CAMERAS,
            'physical_completion': {
                'criterion': 'travel_progress', 'motion_source': 'trace.jsonl',
                'position_key': 'position_m', 'minimum_progress_m': 4,
                'minimum_samples': 2,
                'engineering_tolerances_not_legal': True},
            'case': {
                'case_id': case_id, 'endpoint': case.endpoint,
                'halt_activity': case.activity,
                'exception_probe': case.exception_probe,
                'recording_description': description}}
        files = [{'path': name,
                  'source': str((ROOT / name).relative_to(ROOT.parents[1])),
                  'content': (ROOT / name).read_text(encoding='utf-8')}
                 for name in FILES]
        files.append({'path': 'config.json',
                      'content': json.dumps(config, indent=2, ensure_ascii=False) + '\n'})
        construction = {
            'law_id': LAW, 'cell_id': 'C135705',
            'actor': 'motor_vehicle_driver', 'case_id': case_id,
            'entrypoint': 'runner.py', 'files': files,
            'measurement_plan': [{
                'name': 'highway_side_two_vehicle_halt_and_exception_context',
                'method': 'analysis.analyze',
                'sources': ['parking-site.json', 'parking-history.jsonl',
                            'video_frames.jsonl', 'trace.jsonl']}],
            'recording_description': description,
            'static_checks': [
                'exact case and reviewed original highway, curb and map source hashes',
                'distinct motor vehicles, roadward normal, side and behind targets',
                'edge vehicle stationarity, ego halt and original authority sources'],
            'termination_rules': [
                '45 seconds at 20 Hz with approach and terminal stop, stand or park',
                'failed frame join, source readback, cleanup or restoration rejects capture'],
            'mechanisms': [
                'reviewed highway, curb and map source gate',
                'source-bound edge and ego motor vehicles',
                'ego halt controller and stationary edge vehicle',
                'four synchronized cameras and original frame map',
                'saved-only source-bound finalizer']}
        folder = ROOT if index == 0 else ROOT / 'cases' / case.case_id
        write(folder / 'config.json', config)
        write(folder / 'construction.json', construction)


if __name__ == '__main__':
    main()
