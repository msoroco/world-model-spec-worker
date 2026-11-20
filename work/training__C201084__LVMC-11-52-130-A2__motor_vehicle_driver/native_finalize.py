"""Saved-only C201084 source finalization; no physical or legal acceptance."""
import argparse
import json
from math import isfinite
from pathlib import Path

from fire_lane_survey import CAMERAS, require
from source_measurement import analyze, camera_sources, read_lines, sha, vector


ASSIGNMENT = 'training__C201084__LVMC-11-52-130-A2__motor_vehicle_driver'
CHANNELS = ('ego_pose', 'ego_speed', 'vehicle_stops_in_posted_fire_lane')


def _write_new(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def finalize(attempt, output):
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    require(output.parent == attempt and not output.exists(),
            'Finalization needs a fresh report inside the saved attempt')
    require(not (attempt/'result.json').exists(),
            'Retain previous Native result; use a fresh attempt')
    config = json.loads((attempt/'config.json').read_text())
    case = config.get('case_suffix')
    require(case in ('reference', 'contrast') and
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
    measured = analyze(attempt, case, diagnostic=diagnostic)
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
    channels = {name: [] for name in CHANNELS}
    traces = []
    for actor, frame, sample in zip(actors, frames, measured['samples']):
        at = {'frame': frame['carla_frame'], 'time_s': frame['time_s']}
        pose = actor['ego_pose_xyz_m']
        channels['ego_pose'].append({**at, 'position_xyz_m': pose,
            'yaw_deg': actor['ego_yaw_deg'],
            'body_vertices_xyz_m': actor['ego_body_vertices_xyz_m']})
        channels['ego_speed'].append({**at,
            'speed_mps': sample['speed_mps'],
            'velocity_xyz_mps': actor['ego_velocity_xyz_mps'],
            'speed_provenance': measured['source_kind']})
        channels['vehicle_stops_in_posted_fire_lane'].append({
            **at,
            'value': None,
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
                       'velocity_mps': actor['ego_velocity_xyz_mps'],
                       'speed_provenance': measured['source_kind'],
                       'source_actor_sha256': sources['native-actors.jsonl']})
    source_context = {'map_name': json.loads(
        (attempt/'native-survey-readback.json').read_text())['map_name'],
        'road_id': json.loads(
        (attempt/'native-survey-readback.json').read_text())['fixed_context']['road_id'],
        'sign_actor_id': actors[0]['sign_actor_id'],
        'survey_source_sha256': sources['native-survey-readback.json'],
        'original_sign_text_verified': False,
        'fire_code_designation_verified': False}
    channel_dir = attempt/'channels'
    require(not channel_dir.exists() and
            not (attempt/'trace.jsonl').exists() and
            not (attempt/'recorded-context.json').exists(),
            'Retain previous derived output; use a fresh stage')
    channel_dir.mkdir()
    for name, values in channels.items():
        (channel_dir/(name+'.jsonl')).write_text(
            ''.join(json.dumps(row, allow_nan=False)+'\n' for row in values))
    (attempt/'trace.jsonl').write_text(
        ''.join(json.dumps(row, allow_nan=False)+'\n' for row in traces))
    _write_new(attempt/'recorded-context.json', source_context)
    sources['trace.jsonl'] = sha(attempt/'trace.jsonl')
    sampled_target = (measured['near_zero_with_zone_overlap_frames'] > 0
                      if case == 'reference' else
                      measured['near_zero_disjoint_frames'] > 0)
    target = {
        'target': 'sampled near-zero stop and authored-zone body relation',
        'requested': case == 'reference',
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
