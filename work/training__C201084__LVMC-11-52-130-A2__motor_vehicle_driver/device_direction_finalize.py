"""Saved-only C201084 source finalization; no physical or legal acceptance."""
import argparse
import json
from math import isfinite
from pathlib import Path
from shapely.geometry import Polygon

from fire_lane_survey import CAMERAS, require
from source_measurement import analyze, camera_sources, read_lines, sha, vector
from device_direction_runner import finalize_device


ASSIGNMENT = 'training__C201084__LVMC-11-52-130-A2__motor_vehicle_driver'
CHANNELS = ('ego_pose', 'ego_speed', 'vehicle_stops_in_posted_fire_lane')


def measure_device_direction_context(measured):
    return {key: measured[key] for key in
            ('source_frames','device_actor_id','state_counts',
             'direction_applicability_verified','statutory_necessity_verified')}


def measure_stop_exception_context(measured):
    """Report sampled motion and traffic context without deciding a statutory exception."""
    return {'near_zero_with_authored_overlap_frames':
            measured['near_zero_with_zone_overlap_frames'],
            'near_zero_disjoint_frames': measured['near_zero_disjoint_frames'],
            'following_vehicle_observed': all(
                sample['following_gap_m'] >= 0 for sample in measured['samples']),
            'police_direction_verified': False,
            'traffic_control_direction_verified': False,
            'conflict_necessity_verified': False}


def measure_posted_curb_context(measured, survey):
    """Keep authored curb overlap distinct from verified posting/designation."""
    return {'authored_zone_overlap_frames': sum(
                sample['body_zone_overlap_m2'] > 0 for sample in measured['samples']),
            'authored_zone_area_m2': Polygon(survey['survey_geometry'][
                'authored_fire_lane_polygon_xy_m']).area,
            'sign_actor_id': survey['sign_readback']['actor_id'],
            'original_sign_text_verified': False,
            'fire_code_designation_verified': False}


def measure_public_access_scope(measured, survey):
    """Retain the surveyed road identity and sampled destination relation."""
    return {'road_id': survey['fixed_context']['road_id'],
            'sampled_stop_in_authored_zone':
                measured['near_zero_with_zone_overlap_frames'] > 0,
            'public_access_legally_verified': False,
            'source_kind': measured['source_kind']}


def _write_new(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def _retain_or_verify(path, content):
    """Saved stages may carry derived originals; reuse only byte-identical output."""
    if path.exists():
        require(path.is_file() and path.read_text() == content,
                'Prior derived output differs from retained sources: '+path.name)
    else:
        path.write_text(content)


def finalize(attempt, output):
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    require(output.parent == attempt and not output.exists(),
            'Finalization needs a fresh report inside the saved attempt')
    require(not (attempt/'result.json').exists(),
            'Retain previous Native result; use a fresh attempt')
    config = json.loads((attempt/'config.json').read_text())
    case = config.get('case_suffix')
    require(case == 'device_direction' and
            config.get('case_id') == ASSIGNMENT+'__'+case and
            config.get('selected_case_id') == config['case_id'] and
            config.get('law_id') == 'LVMC-11-52-130-A2' and
            config.get('rate_hz') == 20 and
            config.get('frames') == 600 and
            config.get('duration_s') == 30,
            'Exact fire-lane source config differs')
    description = config.get('recording_description', {})
    require([row.get('name') for row in description.get('channels', [])] ==
            list(CHANNELS), 'Recorded source channel contract differs')
    marker_path = attempt/'acquisition-provenance.json'
    require(marker_path.is_file(), 'Missing explicit acquisition provenance')
    provenance = json.loads(marker_path.read_text())
    diagnostic = (provenance.get('provenance_kind') == 'synthetic_fixture' and
                  provenance.get('diagnostic_fixture') is True)
    original = (provenance.get('provenance_kind') == 'native' and
                provenance.get('diagnostic_fixture') is False)
    require(diagnostic or original,
            'Acquisition provenance must distinguish original from fixture')
    require((attempt/'native-survey-readback.json').is_file(),
            'Missing required source: native-survey-readback.json')
    measured = analyze(attempt, 'reference', diagnostic=diagnostic)
    device_measurement = finalize_device(attempt)
    survey = json.loads((attempt/'native-survey-readback.json').read_text())
    videos = (camera_sources(attempt, measured['frames']) if diagnostic
              else measured['source_camera_videos'])
    require(set(videos) == set(CAMERAS),
            'Saved four-camera source set differs')
    actors = read_lines(attempt/'native-actors.jsonl')
    frames = read_lines(attempt/'video_frames.jsonl')
    require(len(actors) == len(frames) == measured['frames'],
            'Saved source rows differ')
    for actor in actors:
        require(vector(actor.get('ego_pose_xyz_m'), 3) and
                type(actor.get('ego_yaw_deg')) in (int, float) and
                isfinite(actor['ego_yaw_deg']),
                'Missing retained ego pose for recorded channels')
    sources = {
        'native-actors.jsonl': measured['actor_source_sha256'],
        'video_frames.jsonl': measured['frame_map_sha256'],
        'native-survey-readback.json': measured['survey_readback_sha256'],
        'acquisition-provenance.json': sha(marker_path),
    }
    sources.update({item['path']: item['sha256'] for item in videos.values()})
    sources.update(device_measurement['source_sha256'])
    channels = {name: [] for name in CHANNELS}
    traces = []
    for actor, frame, sample in zip(actors, frames, measured['samples']):
        at = {'frame': frame['carla_frame'], 'time_s': frame['time_s']}
        pose = actor['ego_pose_xyz_m']
        channels['ego_pose'].append({**at, 'value': pose, 'position_xyz_m': pose,
            'yaw_deg': actor['ego_yaw_deg'],
            'body_vertices_xyz_m': actor['ego_body_vertices_xyz_m']})
        channels['ego_speed'].append({**at, 'value': sample['speed_mps'],
            'speed_mps': sample['speed_mps'],
            'velocity_xyz_mps': actor['ego_velocity_xyz_mps'],
            'speed_provenance': measured['source_kind']})
        channels['vehicle_stops_in_posted_fire_lane'].append({
            **at,
            'value': (sample['speed_mps'] <= 0.05 and
                      sample['body_zone_overlap_m2'] > 0) if diagnostic else None,
            'value_basis': ('synthetic_authored_zone_only' if diagnostic else
                            'original_posting_review_pending'),
            'sampled_near_zero_motion': sample['speed_mps'] <= 0.05,
            'authored_zone_overlap_m2': sample['body_zone_overlap_m2'],
            'sampled_body_fully_in_authored_zone':
                sample['body_fully_in_authored_zone'],
            'original_sign_text_verified': False,
            'fire_code_designation_verified': False})
        traces.append({**at, 'position_m': pose[:2],
                       'position': {'x': pose[0], 'y': pose[1], 'z': pose[2]},
                       'heading_deg': actor['ego_yaw_deg'],
                       'speed_mps': sample['speed_mps'],
                       'speed_mph': sample['speed_mps']/0.44704,
                       'control': {},
                       'velocity_mps': actor['ego_velocity_xyz_mps'],
                       'speed_provenance': measured['source_kind'],
                       'source_actor_sha256': sources['native-actors.jsonl']})
    source_context = {'map_name': json.loads(
        (attempt/'native-survey-readback.json').read_text())['map_name'],
        'device_direction_context': measure_device_direction_context(device_measurement),
        'original_map_sign_and_fire_lane_survey': {
            'source_kind': measured['source_kind'],
            'survey_source_sha256': sources['native-survey-readback.json'],
            'posting_designation_verified': False,
            'original_sign_text_verified': False},
        'road_id': json.loads(
        (attempt/'native-survey-readback.json').read_text())['fixed_context']['road_id'],
        'sign_actor_id': actors[0]['sign_actor_id'],
        'survey_source_sha256': sources['native-survey-readback.json'],
        'original_sign_text_verified': False,
        'fire_code_designation_verified': False}
    channel_dir = attempt/'channels'
    require(not channel_dir.exists(),
            'Retain previous derived channels; use a fresh stage')
    channel_dir.mkdir()
    for name, values in channels.items():
        (channel_dir/(name+'.jsonl')).write_text(
            ''.join(json.dumps(row, allow_nan=False)+'\n' for row in values))
    _retain_or_verify(attempt/'trace.jsonl',
        ''.join(json.dumps(row, allow_nan=False)+'\n' for row in traces))
    _retain_or_verify(attempt/'recorded-context.json',
                      json.dumps(source_context, indent=2, allow_nan=False)+'\n')
    sources['trace.jsonl'] = sha(attempt/'trace.jsonl')
    sampled_target = (measured['near_zero_with_zone_overlap_frames'] > 0
                      if case == 'device_direction' else
                      measured['near_zero_disjoint_frames'] > 0)
    target = {
        'target': 'sampled near-zero stop and authored-zone body relation',
        'requested': case == 'device_direction',
        'measured': measured['near_zero_with_zone_overlap_frames'] > 0,
        'method': 'source-joined velocity and body polygon against authored zone',
        'tolerance': '0.05 m/s engineering sample tolerance; no legal threshold',
        'matched': sampled_target,
        'physical_cause_confirmed': False,
        'cause_evidence': ['native-actors.jsonl','video_frames.jsonl',
                           'native-survey-readback.json']}
    check = {'status': 'unverified',
             'method': 'independent original pixel, posting and exception review required',
             'sources': sources, 'intervals': [],
             'physical_causation_claimed': False,
             'legal_verdict_claimed': False}
    result = {
        'case_id': config['case_id'],
        'measured_values': {
            'device_state_counts': device_measurement['state_counts'],
            'source_frames': measured['frames'],
            'near_zero_with_authored_zone_overlap_frames':
                measured['near_zero_with_zone_overlap_frames'],
            'near_zero_disjoint_from_authored_zone_frames':
                measured['near_zero_disjoint_frames'],
            'original_sign_text_verified': False,
            'fire_code_designation_verified': False},
        'target_checks': [target],
        'setup_confirmed': False, 'behavior_attempted': True,
        'maneuver_completed': False,
        'physical_checks': {name: dict(check) for name in
                            ('setup','target','maneuver')},
        'physical_failure_flags': ['posting_designation_and_exceptions_unreviewed']+
                                  ([] if sampled_target else ['sampled_stop_target_not_met']),
        'termination_reason': 'saved source analysis; physical and legal review pending',
        'trace_reference': 'trace.jsonl',
        'video_references': [name+'.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': description,
        'recording_evidence': [
            {'name': row['name'], 'unit': row['unit'],
             'reference': 'channels/'+row['name']+'.jsonl'}
            for row in description['channels']] + [
            {'name': row['name'], 'unit': row['unit'],
             'reference': 'recorded-context.json'}
            for row in description.get('context_inputs', [])],
        'realized_observables': {
            'sampled_authored_zone_overlap_stopped_frames': {
                'value': measured['near_zero_with_zone_overlap_frames'],
                'unit': 'count', 'statistic': 'frame_count',
                'method': 'saved actor velocity and body polygon overlap',
                'time_window': 'full saved source sequence',
                'reference': 'channels/vehicle_stops_in_posted_fire_lane.jsonl'}},
        'provenance_kind': 'synthetic_fixture' if diagnostic else 'native',
        'diagnostic_fixture': diagnostic, 'accepted': False,
        'physical_acceptance_claimed': False,
        'legal_verdict_claimed': False}
    _write_new(attempt/'result.json', result)
    report = {
        'format': 'worker-analysis-report', 'case_id': config['case_id'],
        'measurements': {
            'device_direction_context': {
                'value': measure_device_direction_context(device_measurement),
                'method': 'measure_device_direction_context',
                'sources': device_measurement['source_sha256']},
            'stop_exception_context': {
                'value': measure_stop_exception_context(measured),
                'method': 'measure_stop_exception_context',
                'sources': {key: sources[key] for key in
                            ('native-actors.jsonl', 'video_frames.jsonl')}},
            'posted_curb_context': {
                'value': measure_posted_curb_context(measured, survey),
                'method': 'measure_posted_curb_context',
                'sources': {key: sources[key] for key in
                            ('native-survey-readback.json', 'native-actors.jsonl')}},
            'public_access_scope': {
                'value': measure_public_access_scope(measured, survey),
                'method': 'measure_public_access_scope',
                'sources': {key: sources[key] for key in
                            ('native-survey-readback.json', 'native-actors.jsonl')}},
            'authored_zone_stop': {
                'value': {'near_zero_with_overlap_frames':
                          measured['near_zero_with_zone_overlap_frames'],
                          'near_zero_disjoint_frames':
                          measured['near_zero_disjoint_frames'],
                          'original_sign_text_verified': False,
                          'fire_code_designation_verified': False},
                'method': 'saved source velocity, body, map and video join',
                'sources': sources}},
        'source_sha256': sources,
        'physical_checks': result['physical_checks'],
        'realized_observables': result['realized_observables'],
        'provenance_kind': result['provenance_kind'],
        'diagnostic_fixture': diagnostic,
        'analysis_complete': True,
        'physical_acceptance_claimed': False,
        'legal_verdict_claimed': False,
        'limitations': ['Sign-face text and Fire Code designation unverified',
                        'Statutory exceptions and physical completion require independent review']}
    _write_new(output, report)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)


if __name__ == '__main__':
    main()
