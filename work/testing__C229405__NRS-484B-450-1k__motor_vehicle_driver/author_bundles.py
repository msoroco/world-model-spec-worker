"""Materialize seven exact roadwork constructions with source-bound code bytes."""
from __future__ import annotations

import json
from pathlib import Path

from excavation_park import CASES

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
LAW = 'NRS-484B-450-1k'
FILES = ('runner.py', 'native_excavation.py', 'site_review.py',
         'excavation_park.py', 'analysis.py',
         'tests/test_excavation_park.py', 'tests/test_site_review.py')
CAMERAS = [
    {'name': name, 'width': width, 'height': height,
     'pose_strategy': strategy, 'fov_deg': 90}
    for name, width, height, strategy in (
        ('overview', 1920, 1080, 'fixed roadwork site, excavation and both vehicles'),
        ('approach', 1280, 720, 'fixed road approach and passing traffic route'),
        ('reference_corner', 1280, 720, 'fixed excavation edge, lane span and ego body'),
        ('driver_reference', 1280, 720, 'ego mounted roadwork approach view'))]
CHANNELS = ('site_source', 'excavation_extent', 'vehicle_body_history',
            'vehicle_motion_history', 'traffic_motion_history', 'passage_history',
            'halt_activity_history', 'exception_context', 'camera_frame_map')
CONTEXT = ('highway_status', 'driver_identity', 'motor_vehicle_class',
           'excavation_status', 'traffic_conflict_necessity', 'law_compliance',
           'officer_direction', 'official_device_direction')


def recording():
    return {
        'channels': [
            {'name': name, 'unit': 'structured record', 'sampling_rate_hz': 20,
             'method': 'Original Native frame acquisition and saved-only extraction',
             'time_window': 'roadwork approach through terminal halt',
             'reference_frame': 'original CARLA world frame and timestamp',
             'uncertainty': '20 Hz sampling and actor bounding-box geometry'}
            for name in CHANNELS],
        'context_inputs': [
            {'name': name, 'unit': 'reviewed source packet',
             'method': 'Reviewed original highway, roadwork and authority source binding'}
            for name in CONTEXT],
        'limitations': [
            'Roadwork marker geometry does not itself establish highway excavation status.',
            'Physical width and traffic motion do not define legal obstruction.',
            'Exception applicability, actual pixels and source equivalence need independent review.']}


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
            'cell_id': 'C229405', 'actor': 'motor_vehicle_driver',
            'rate_hz': 20, 'duration_s': 45,
            'engineering_throttle': 0.25,
            'engineering_braking_factor': 5.0,
            'required_atoms': [], 'source_packets': [],
            'cameras': CAMERAS,
            'physical_completion': {
                'criterion': 'travel_progress', 'motion_source': 'trace.jsonl',
                'position_key': 'position_m', 'minimum_progress_m': 4,
                'minimum_samples': 2,
                'engineering_tolerances_not_legal': True},
            'case': {
                'case_id': case_id, 'relation': case.relation,
                'halt_activity': case.activity, 'passage_probe': case.passage,
                'exception_context': case.exception,
                'recording_description': description}}
        files = [{'path': name,
                  'source': str((ROOT / name).relative_to(ROOT.parents[1])),
                  'content': (ROOT / name).read_text(encoding='utf-8')}
                 for name in FILES]
        files.append({'path': 'config.json',
                      'content': json.dumps(config, indent=2, ensure_ascii=False) + '\n'})
        construction = {
            'law_id': LAW, 'cell_id': 'C229405',
            'actor': 'motor_vehicle_driver', 'case_id': case_id,
            'entrypoint': 'runner.py', 'files': files,
            'measurement_plan': [{
                'name': 'excavation_body_passage_and_exception_context',
                'method': 'analysis.analyze',
                'sources': ['excavation-site.json', 'excavation-history.jsonl',
                            'video_frames.jsonl', 'trace.jsonl']}],
            'recording_description': description,
            'static_checks': [
                'exact case and reviewed original roadwork source hashes',
                'motor vehicle, passing traffic, excavation markers and route readback',
                'road centerline relation and original body-derived passage width',
                'independently sourced conflict, officer, device and law contexts'],
            'termination_rules': [
                '45 seconds at 20 Hz with approach and terminal stop, stand or park',
                'failed frame join, source readback, cleanup or restoration rejects capture'],
            'mechanisms': [
                'reviewed highway and excavation source gate',
                'source-bound roadwork markers and two motor vehicles',
                'ego halt controller and passing traffic controller',
                'four synchronized cameras and original frame map',
                'saved-only source-bound finalizer']}
        folder = ROOT if index == 0 else ROOT / 'cases' / case.case_id
        write(folder / 'config.json', config)
        write(folder / 'construction.json', construction)


if __name__ == '__main__':
    main()
