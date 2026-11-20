"""Remeasure optional-lead traffic-pair attempts from saved original sources."""
import json
from pathlib import Path

from exception_measurement import analyze as analyze_lead
from fire_lane_survey import require
from source_measurement import analyze as analyze_stop, read_lines


def analyze(attempt, *, diagnostic=False):
    attempt = Path(attempt)
    survey = json.loads((attempt/'native-survey-readback.json').read_text())
    pair = survey.get('traffic_pair')
    require(isinstance(pair, dict) and
            type(pair.get('lead_present')) is bool and
            pair.get('destination_xy_m') == [30, 1] and
            pair.get('statutory_necessity_verified') is False,
            'Traffic-pair source plan incomplete or overclaims necessity')
    stop = analyze_stop(attempt, 'reference', diagnostic=diagnostic)
    actors = read_lines(attempt/'native-actors.jsonl')
    require(len(actors) == stop['frames'] and
            all(row.get('lead_present') is pair['lead_present'] and
                row.get('physical_completion_claimed') is False and
                row.get('statutory_necessity_claimed') is False
                for row in actors),
            'Traffic-pair source lead mode, rows or completion claim differ')
    if pair['lead_present']:
        require(all(type(row.get('lead_actor_id')) is int for row in actors),
                'Present-lead source lacks actor identities')
        lead = analyze_lead(attempt, diagnostic=diagnostic)
        lead_frames = lead['lead_ahead_frames']
        lead_id = lead['lead_actor_id']
        lead_samples = lead['samples']
    else:
        require(all(not any(key.startswith('lead_') for key in row if
                            key != 'lead_present') for row in actors),
                'Absent-lead source contains a lead actor field')
        lead_frames, lead_id = 0, None
        lead_samples = [None]*stop['frames']
    samples = []
    for actor, stop_sample, lead_sample in zip(
            actors, stop['samples'], lead_samples):
        samples.append({
            'carla_frame':stop_sample['carla_frame'],
            'time_s':stop_sample['time_s'],
            'ego_speed_mps':stop_sample['speed_mps'],
            'ego_body_zone_overlap_m2':stop_sample['body_zone_overlap_m2'],
            'lead_present':pair['lead_present'],
            'lead_longitudinal_gap_m':(
                lead_sample['lead_longitudinal_gap_m']
                if lead_sample is not None else None),
            'lead_brake_requested':actor['requested_control'].get(
                'control_basis') == 'observed_lead_braking_request',
        })
    return {'format':'c201084-traffic-pair-source-measurement-v1',
            'source_kind':stop['source_kind'],
            'frames':stop['frames'],
            'lead_present':pair['lead_present'],
            'lead_actor_id':lead_id,
            'lead_ahead_frames':lead_frames,
            'samples':samples,
            'lead_brake_request_frames':sum(
                row['requested_control'].get('control_basis') ==
                'observed_lead_braking_request' for row in actors),
            'near_zero_with_zone_overlap_frames':
                stop['near_zero_with_zone_overlap_frames'],
            'near_zero_disjoint_frames':stop['near_zero_disjoint_frames'],
            'actor_source_sha256':stop['actor_source_sha256'],
            'frame_map_sha256':stop['frame_map_sha256'],
            'survey_readback_sha256':stop['survey_readback_sha256'],
            'source_camera_videos':stop['source_camera_videos'],
            'statutory_necessity_verified':False,
            'physical_or_legal_completion_claimed':False}
