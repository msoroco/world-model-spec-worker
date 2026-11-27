"""Materialize fifteen exact entrance constructions from reviewed case targets."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

from fire_station_scene import ASSIGNMENT, CASES, LAW


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
FILES = ('runner.py', 'native_fire_station.py', 'site_review.py',
         'analysis.py',
         'fire_station_scene.py', 'fire_entrance_measurements.py',
         'case-plan.json',
         'tests/test_fire_station_scene.py',
         'tests/test_fire_entrance_measurements.py')
CAMERAS = [
    {'name': name, 'width': width, 'height': height,
     'pose_strategy': strategy, 'fov_deg': 90}
    for name, width, height, strategy in (
        ('overview', 1920, 1080, 'fixed entrance and both highway sides'),
        ('approach', 1280, 720, 'fixed vehicle approach and terminal halt'),
        ('reference_corner', 1280, 720, 'fixed driveway edge and ego body'),
        ('driver_reference', 1280, 720, 'ego mounted approach view'))]
CHANNELS = ('entrance_boundary', 'vehicle_body_history', 'vehicle_motion_history',
            'highway_side_history', 'halt_activity_history', 'traffic_motion_history',
            'exception_context', 'camera_frame_map')
CONTEXT = ('station_identity', 'highway_boundary', 'highway_dedication',
           'public_vehicular_use', 'stopping_person', 'halt_purpose',
           'traffic_conflict', 'law_direction', 'police_direction',
           'official_device_direction')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n',
                    encoding='utf-8')


def recording():
    return {
        'channels': [
            {'name': name, 'unit': 'structured original Native observation',
             'sampling_rate_hz': 20,
             'method': 'original Native frame acquisition and saved-only extraction',
             'time_window': 'approach through terminal halt',
             'reference_frame': 'original CARLA world frame and timestamp',
             'uncertainty': '20 Hz sampling and original bounding-box vertices'}
            for name in CHANNELS],
        'context_inputs': [
            {'name': name, 'unit': 'reviewed source packet',
             'method': 'independent original station, highway, person and authority review'}
            for name in CONTEXT],
        'limitations': [
            'Markers do not establish fire-station identity or public highway status.',
            'Nominal foot distances are construction targets; original body vertices are measured.',
            'Exact legal distance convention and exception applicability remain unresolved.']}


def main():
    ids = [case.case_id for case in CASES]
    description = recording()
    code_files = [{'path': name,
                   'source': str((ROOT / name).relative_to(REPO)),
                   'content': (ROOT / name).read_text(encoding='utf-8')}
                  for name in FILES]
    for index, case in enumerate(CASES):
        config = {
            'assignment_id': ASSIGNMENT,
            'selected_case_id': case.case_id,
            'supported_case_ids': ids,
            'law_id': LAW, 'cell_id': 'C229925',
            'actor': 'vehicle_stopping_person',
            'rate_hz': 20, 'duration_s': 45,
            'engineering_throttle': .25,
            'engineering_braking_factor': 5.0,
            'required_atoms': [], 'source_packets': [],
            'cameras': CAMERAS,
            'physical_completion': {
                'criterion': 'travel_progress',
                'motion_source': 'trace.jsonl',
                'position_key': 'position_m',
                'minimum_progress_m': 4, 'minimum_samples': 2,
                'engineering_tolerances_not_legal': True},
            'case': {
                'case_id': case.case_id,
                'side_request': case.side,
                'activity_request': case.activity,
                'nominal_entrance_distance_ft': case.distance_ft,
                'circumstance_request': case.circumstance,
                'recording_description': description}}
        files = list(code_files) + [
            {'path': 'config.json',
             'content': json.dumps(config, indent=2, ensure_ascii=False) + '\n'}]
        construction = {
            'law_id': LAW, 'cell_id': 'C229925',
            'actor': 'vehicle_stopping_person',
            'case_id': case.case_id,
            'entrypoint': 'runner.py', 'files': files,
            'measurement_plan': [
                {'name': 'fire_entrance_body_side_activity_and_exception',
                 'method': 'analysis.analyze',
                 'sources': ['fire-entrance-context.json',
                             'fire-entrance-trace.jsonl',
                             'fire-source-receipt.json',
                             'video_frames.jsonl', 'trace.jsonl']}],
            'recording_description': description,
            'static_checks': [
                'exact case and original reviewed source hashes',
                'fire-station identity, entrance segment and public-highway evidence',
                'opposite or entrance side from source-bound geometry',
                'vehicle eight-vertex body distance and original 20 Hz frames',
                'independent stopping person, activity and exception context'],
            'termination_rules': [
                '45 seconds at 20 Hz with approach and terminal halt',
                'failed frame join, source readback, cleanup or restoration rejects capture'],
            'mechanisms': [
                'reviewed original station, entrance, highway and authority source gate',
                'source-bound driveway markers and qualifying vehicle',
                'halt controller and physical conflict vehicle where applicable',
                'four synchronized cameras and original frame map',
                'saved-only source-bound entrance finalizer']}
        folder = ROOT if index == 0 else ROOT / 'cases' / case.name
        write(folder / 'config.json', config)
        write(folder / 'construction.json', construction)
    plan = json.loads((ROOT / 'case-plan.json').read_text(encoding='utf-8'))
    evidence_path = REPO / 'inputs' / ASSIGNMENT / 'evidence.json'
    plan['evidence_review']['gaps'] = [{
        'id': 'no-accepted-recording',
        'requirement': 'Original fire-station entrance and public-highway source evidence',
        'source': str(evidence_path.relative_to(REPO)),
        'source_sha256': hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
        'why_existing_insufficient': 'Frozen inventory contains no accepted original recording for the 20-foot and opposite-side 75-foot clauses.'}]
    for item in plan['cases']:
        item['gap_ids'] = ['no-accepted-recording']
        item['recording_description'] = description
        item['physical_risk'] = ('Native vehicle may not hold a stable body position near '
                                 'the nominal entrance-distance target; original motion '
                                 'and pixels require local review.')
    for index, pair in enumerate(plan['comparisons']):
        pair.setdefault('comparison_id',
                        'entrance_' + str(index + 1).zfill(2) + '_' +
                        pair['case_ids'][1].split('__')[-1])
    plan['requirement_dispositions'] = [
        {'requirement': 'NRS 484B.450(1)(j) fire-station driveway entrance, '
                        '20/75-foot placements and stated exceptions',
         'source': 'inputs/' + ASSIGNMENT + '/assignment.json',
         'status': 'selected_required', 'case_ids': ids,
         'evidence_or_gap': 'No accepted recordings; fifteen source-gated exact captures required.'}]
    plan['source_observation_mapping'] = {}
    plan['observations'] = [
        {'name': name, 'mandatory': True,
         'description': 'Original source-bound ' + name.replace('_', ' ')}
        for name in CHANNELS]
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 45,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': name, 'subject': subject,
             'interval': 'approach through terminal halt'}
            for name, subject in (
                ('overview', 'station entrance and both highway sides'),
                ('approach', 'vehicle approach and halt'),
                ('reference_corner', 'entrance endpoints and vehicle body'),
                ('driver_reference', 'subject approach view'))]}
    plan['runtime_uncertainties'] = [
        'Original CARLA entrance, station identity and public-highway basis require local review.',
        'Measured body distances do not settle a legal distance convention.',
        'Exception necessity and official authority require independent legal review.']
    plan['planning_status'] = 'selected_cpu_package_in_progress'
    write(ROOT / 'case-plan.json', plan)
    write(ROOT / 'measurement-contract.json', {
        'format': 'worker-measurement-contract',
        'requirements': [
            {'disposition_index': 0,
             'requirement': plan['requirement_dispositions'][0]['requirement'],
             'source': 'inputs/' + ASSIGNMENT + '/assignment.json',
             'output_key': 'fire_entrance_body_side_activity_and_exception',
             'method': 'analyze', 'value_type': 'object', 'kind': 'measured',
             'inputs': ['fire-entrance-context.json',
                        'fire-entrance-trace.jsonl',
                        'fire-source-receipt.json',
                        'trace.jsonl', 'video_frames.jsonl']}],
        'negative': {'remove': ['fire-entrance-context.json'],
                     'error_contains': 'Missing required source: fire-entrance-context.json'}})


if __name__ == '__main__':
    main()
