"""Saved-only optional-lead pair finalizer; original review remains required."""
import argparse
import json
from pathlib import Path

from traffic_pair_measurement import analyze
from fire_lane_survey import CAMERAS, require
from source_measurement import camera_sources, read_lines, sha


ASSIGNMENT = 'training__C201084__LVMC-11-52-130-A2__motor_vehicle_driver'
CHANNELS = ('ego_pose', 'ego_speed', 'vehicle_stops_in_posted_fire_lane',
            'lead_traffic_presence')


def measure_traffic_pair_context(measured):
    return {'lead_present': measured['lead_present'],
            'lead_ahead_frames': measured['lead_ahead_frames'],
            'lead_brake_request_frames': measured['lead_brake_request_frames'],
            'near_zero_with_zone_overlap_frames':
                measured['near_zero_with_zone_overlap_frames'],
            'statutory_necessity_verified': False}


def measure_posted_curb_context(measured, survey):
    return {'authored_zone_overlap_frames': sum(
                sample['ego_body_zone_overlap_m2'] > 0
                for sample in measured['samples']),
            'sign_actor_id': survey['sign_readback']['actor_id'],
            'original_sign_text_verified': False,
            'fire_code_designation_verified': False}


def measure_public_access_scope(measured, survey):
    return {'road_id': survey['fixed_context']['road_id'],
            'sampled_stop_in_authored_zone':
                measured['near_zero_with_zone_overlap_frames'] > 0,
            'public_access_legally_verified': False,
            'source_kind': measured['source_kind']}


def _write_new(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def finalize(attempt, output):
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    require(output.parent == attempt and not output.exists() and
            not (attempt/'result.json').exists(),
            'Finalization needs a fresh report and result inside the saved attempt')
    config = json.loads((attempt/'config.json').read_text())
    mode = config.get('case_suffix')
    require(mode in ('near_lead', 'absent_lead'),
            'Unknown traffic-pair case suffix')
    case_id = ASSIGNMENT+'__'+mode
    require(config.get('case_id') == case_id and
            config.get('selected_case_id') == case_id and
            config.get('case_suffix') == mode and
            config.get('law_id') == 'LVMC-11-52-130-A2' and
            config.get('rate_hz') == 20 and config.get('frames') == 600 and
            config.get('duration_s') == 30 and
            config.get('physical_acceptance_claimed') is False and
            config.get('legal_verdict') is None,
            'Exact traffic-pair source config differs')
    description = config.get('recording_description', {})
    require([row.get('name') for row in description.get('channels', [])] ==
            list(CHANNELS), 'Traffic-pair source channel contract differs')
    marker = attempt/'acquisition-provenance.json'
    require(marker.is_file(), 'Missing explicit acquisition provenance')
    provenance = json.loads(marker.read_text())
    diagnostic = (provenance.get('provenance_kind') == 'synthetic_fixture' and
                  provenance.get('diagnostic_fixture') is True)
    original = (provenance.get('provenance_kind') == 'native' and
                provenance.get('diagnostic_fixture') is False)
    require(diagnostic or original,
            'Acquisition provenance must distinguish original from fixture')
    require((attempt/'native-survey-readback.json').is_file(),
            'Missing required source: native-survey-readback.json')
    measured = analyze(attempt, diagnostic=diagnostic)
    videos = (camera_sources(attempt, measured['frames']) if diagnostic else
              measured['source_camera_videos'])
    require(set(videos) == set(CAMERAS),
            'Saved four-camera source set differs')
    actors = read_lines(attempt/'native-actors.jsonl')
    frames = read_lines(attempt/'video_frames.jsonl')
    require(len(actors) == len(frames) == measured['frames'],
            'Saved traffic-pair source rows differ')
    sources = {
        'native-actors.jsonl': measured['actor_source_sha256'],
        'video_frames.jsonl': measured['frame_map_sha256'],
        'native-survey-readback.json': measured['survey_readback_sha256'],
        'acquisition-provenance.json': sha(marker)}
    sources.update({video['path']: video['sha256'] for video in videos.values()})
    channels = {name: [] for name in CHANNELS}
    trace = []
    for actor, frame, sample in zip(actors, frames, measured['samples']):
        at = {'frame': frame['carla_frame'], 'time_s': frame['time_s']}
        pose = actor['ego_pose_xyz_m']
        channels['ego_pose'].append({**at, 'value': pose,
            'position_xyz_m': pose, 'yaw_deg': actor['ego_yaw_deg'],
            'body_vertices_xyz_m': actor['ego_body_vertices_xyz_m']})
        channels['ego_speed'].append({**at, 'value': sample['ego_speed_mps'],
            'speed_mps': sample['ego_speed_mps'],
            'velocity_xyz_mps': actor['ego_velocity_xyz_mps'],
            'speed_provenance': measured['source_kind']})
        channels['vehicle_stops_in_posted_fire_lane'].append({**at,
            'value': (sample['ego_speed_mps'] <= 0.05 and
                      sample['ego_body_zone_overlap_m2'] > 0) if diagnostic else None,
            'value_basis': 'synthetic_authored_zone_only' if diagnostic else
                           'original_posting_review_pending',
            'sampled_near_zero_motion': sample['ego_speed_mps'] <= 0.05,
            'authored_zone_overlap_m2': sample['ego_body_zone_overlap_m2'],
            'original_sign_text_verified': False,
            'fire_code_designation_verified': False})
        channels['lead_traffic_presence'].append({**at,
            'value': sample['lead_present'],
            'lead_actor_id': measured['lead_actor_id'],
            'longitudinal_gap_m': sample['lead_longitudinal_gap_m'],
            'lead_brake_requested': sample['lead_brake_requested'],
            'statutory_necessity_verified': False})
        trace.append({**at, 'position_m': pose[:2],
            'position': {'x': pose[0], 'y': pose[1], 'z': pose[2]},
            'heading_deg': actor['ego_yaw_deg'],
            'speed_mps': sample['ego_speed_mps'],
            'speed_mph': sample['ego_speed_mps']/0.44704,
            'control': {}, 'velocity_mps': actor['ego_velocity_xyz_mps'],
            'speed_provenance': measured['source_kind'],
            'source_actor_sha256': sources['native-actors.jsonl']})
    channel_dir = attempt/'channels'
    require(not channel_dir.exists(),
            'Retain previous derived channels; use a fresh stage')
    channel_dir.mkdir()
    for name, rows in channels.items():
        (channel_dir/(name+'.jsonl')).write_text(
            ''.join(json.dumps(row, allow_nan=False)+'\n' for row in rows))
    trace_path = attempt/'trace.jsonl'
    if trace_path.exists():
        require(trace_path.read_text() == ''.join(
            json.dumps(row, allow_nan=False)+'\n' for row in trace),
            'Prior trace differs from retained traffic-pair sources')
    else:
        trace_path.write_text(''.join(
            json.dumps(row, allow_nan=False)+'\n' for row in trace))
    sources['trace.jsonl'] = sha(trace_path)
    survey = json.loads((attempt/'native-survey-readback.json').read_text())
    context = {'map_name': survey['map_name'],
        'original_map_sign_and_fire_lane_survey': {
            'source_kind': measured['source_kind'],
            'survey_source_sha256': sources['native-survey-readback.json'],
            'posting_designation_verified': False,
            'original_sign_text_verified': False},
        'road_id': survey['fixed_context']['road_id'],
        'sign_actor_id': actors[0]['sign_actor_id'],
        'lead_actor_id': measured['lead_actor_id'],
        'survey_source_sha256': sources['native-survey-readback.json'],
        'original_sign_text_verified': False,
        'fire_code_designation_verified': False,
        'statutory_necessity_verified': False}
    context_path = attempt/'recorded-context.json'
    context_content = json.dumps(context, indent=2, allow_nan=False)+'\n'
    if context_path.exists():
        require(context_path.read_text() == context_content,
                'Prior context differs from retained traffic-pair sources')
    else:
        context_path.write_text(context_content)
    check = {'status': 'unverified',
        'method': 'independent original pixel, posting and exception review required',
        'sources': sources, 'intervals': [],
        'physical_causation_claimed': False,
        'legal_verdict_claimed': False}
    result = {
        'case_id': case_id,
        'measured_values': {
            'source_frames': measured['frames'],
            'near_zero_with_authored_zone_overlap_frames':
                measured['near_zero_with_zone_overlap_frames'],
            'lead_ahead_frames': measured['lead_ahead_frames'],
            'lead_brake_request_frames': measured['lead_brake_request_frames'],
            'statutory_necessity_verified': False,
            'original_sign_text_verified': False,
            'fire_code_designation_verified': False},
        'target_checks': [{
            'target': 'source-observed lead presence for paired mode',
            'requested': mode == 'near_lead',
            'measured': measured['lead_present'],
            'method': 'saved lead actor identity and frame source',
            'tolerance': 'exact actor presence in all 600 source rows',
            'matched': measured['lead_present'] is (mode == 'near_lead'),
            'physical_cause_confirmed': False,
            'cause_evidence': ['native-actors.jsonl','video_frames.jsonl']}],
        'setup_confirmed': False, 'behavior_attempted': True,
        'maneuver_completed': False,
        'physical_checks': {name: dict(check) for name in
                            ('setup','target','maneuver')},
        'physical_failure_flags': ['posting_designation_and_traffic_necessity_unreviewed'],
        'termination_reason': 'saved traffic-pair source analysis; physical and legal review pending',
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
            'lead_presence_frames': {'value': measured['frames'] if measured['lead_present'] else 0,
                'unit': 'count', 'statistic': 'frame_count',
                'method': 'saved optional lead actor identity',
                'time_window': 'full saved source sequence',
                'reference': 'channels/lead_traffic_presence.jsonl'}},
        'provenance_kind': 'synthetic_fixture' if diagnostic else 'native',
        'diagnostic_fixture': diagnostic, 'accepted': False,
        'physical_acceptance_claimed': False,
        'legal_verdict_claimed': False}
    _write_new(attempt/'result.json', result)
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
        'measurements': {'traffic_pair_context': {
            'value': measure_traffic_pair_context(measured),
            'method': 'measure_traffic_pair_context',
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
                ('native-survey-readback.json', 'native-actors.jsonl')}}},
        'source_sha256': sources,
        'physical_checks': result['physical_checks'],
        'realized_observables': result['realized_observables'],
        'provenance_kind': result['provenance_kind'],
        'diagnostic_fixture': diagnostic,
        'analysis_complete': True,
        'physical_acceptance_claimed': False,
        'legal_verdict_claimed': False,
        'limitations': ['Sign-face text and Fire Code designation unverified',
                        'Statutory traffic necessity and physical completion require independent review']}
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
