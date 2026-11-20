"""Recompute lead traffic relation from saved actor, frame and camera sources."""
import json
from math import cos, hypot, radians, sin
from pathlib import Path

from fire_lane_survey import require
from source_measurement import analyze as analyze_stop, read_lines, vector


def analyze(attempt, *, diagnostic=False):
    attempt = Path(attempt)
    stop = analyze_stop(attempt, 'reference', diagnostic=diagnostic)
    actors = read_lines(attempt/'native-actors.jsonl')
    require(len(actors) == stop['frames'], 'Conflict actor source count differs')
    plan = json.loads((attempt/'native-survey-readback.json').read_text())
    probe = plan.get('conflict_probe')
    require(isinstance(probe, dict) and
            probe.get('statutory_necessity_verified') is False and
            probe.get('original_review_required') is True,
            'Conflict survey must reserve statutory review')
    lead_id, samples = None, []
    for actor, stop_sample in zip(actors, stop['samples']):
        require(actor.get('frame') == stop_sample['carla_frame'] and
                type(actor.get('lead_actor_id')) is int and
                actor.get('lead_road_id') == plan['fixed_context']['road_id'] and
                vector(actor.get('ego_pose_xyz_m'), 3) and
                vector(actor.get('lead_pose_xyz_m'), 3) and
                vector(actor.get('lead_velocity_xyz_mps'), 3) and
                isinstance(actor.get('lead_body_vertices_xyz_m'), list) and
                len(actor['lead_body_vertices_xyz_m']) >= 4 and
                all(vector(v, 3) for v in actor['lead_body_vertices_xyz_m']) and
                type(actor.get('ego_yaw_deg')) in (int, float) and
                actor.get('physical_completion_claimed') is False and
                actor.get('statutory_necessity_claimed') is False,
                'Original lead actor source incomplete or claims a verdict')
        if lead_id is None:
            lead_id = actor['lead_actor_id']
        require(actor['lead_actor_id'] == lead_id and
                lead_id != actor['ego_actor_id'] and
                lead_id != actor['following_actor_id'],
                'Original lead actor identity changed')
        ego = actor['ego_pose_xyz_m']
        lead = actor['lead_pose_xyz_m']
        angle = radians(actor['ego_yaw_deg'])
        forward_x, forward_y = cos(angle), sin(angle)
        dx, dy = lead[0]-ego[0], lead[1]-ego[1]
        longitudinal = dx*forward_x+dy*forward_y
        lateral = -dx*forward_y+dy*forward_x
        ego_v = actor['ego_velocity_xyz_mps']
        lead_v = actor['lead_velocity_xyz_mps']
        closing = ego_v[0]*forward_x+ego_v[1]*forward_y - (
            lead_v[0]*forward_x+lead_v[1]*forward_y)
        samples.append({
            'carla_frame': actor['frame'],
            'time_s': stop_sample['time_s'],
            'lead_longitudinal_gap_m': longitudinal,
            'lead_lateral_offset_m': lateral,
            'lead_speed_mps': hypot(hypot(*lead_v[:2]), lead_v[2]),
            'ego_closing_speed_mps': closing,
            'ego_speed_mps': stop_sample['speed_mps'],
            'ego_body_zone_overlap_m2': stop_sample['body_zone_overlap_m2'],
            'ego_brake_requested': actor.get('requested_control', {}).get('brake') == 1.0,
        })
    return {
        'format': 'c201084-source-conflict-measurement-v1',
        'source_kind': stop['source_kind'],
        'lead_actor_id': lead_id,
        'ego_actor_id': stop['ego_actor_id'],
        'frames': stop['frames'],
        'actor_source_sha256': stop['actor_source_sha256'],
        'frame_map_sha256': stop['frame_map_sha256'],
        'survey_readback_sha256': stop['survey_readback_sha256'],
        'source_camera_videos': stop['source_camera_videos'],
        'samples': samples,
        'near_zero_with_zone_overlap_frames': stop['near_zero_with_zone_overlap_frames'],
        'lead_ahead_frames': sum(s['lead_longitudinal_gap_m'] > 0 for s in samples),
        'brake_request_frames': sum(s['ego_brake_requested'] for s in samples),
        'actual_sign_text_verified': False,
        'fire_code_designation_verified': False,
        'statutory_necessity_verified': False,
        'physical_or_legal_completion_claimed': False,
    }
