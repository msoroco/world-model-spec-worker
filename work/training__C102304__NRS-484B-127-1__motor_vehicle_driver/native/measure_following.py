"""Source-bound moving-leader gap/headway observation without legal cutoff."""
import hashlib
import json
import math
from pathlib import Path
import statistics

RATE_HZ = 20
MIN_FOLLOW_FRAMES = 100


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def point(value, name):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('Missing '+name)
    result = tuple(float(v) for v in value)
    if not all(math.isfinite(v) for v in result):
        raise ValueError('Nonfinite '+name)
    return result


def body_projections(value, forward, name):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError('Missing original full body: '+name)
    points = [point(v, name) for v in value]
    if len({(round(x, 6), round(y, 6)) for x, y in points}) != 4:
        raise ValueError('Degenerate original body: '+name)
    lateral = (-forward[1], forward[0])
    longitudinal = [x*forward[0]+y*forward[1] for x, y in points]
    transverse = [x*lateral[0]+y*lateral[1] for x, y in points]
    return (min(longitudinal), max(longitudinal),
            min(transverse), max(transverse))


def measure(samples_path, context_path):
    samples_path, context_path = Path(samples_path), Path(context_path)
    for path in (samples_path, context_path):
        if not path.is_file():
            raise ValueError('Missing required source: '+path.name)
    context = json.loads(context_path.read_text())
    required = ('native_road_id', 'native_lane_id', 'hill_crest_profile',
                'traffic', 'surface', 'visibility', 'highway_public_availability',
                'apparatus_response_status', 'ego_emergency_business_status')
    if any(key not in context for key in required):
        raise ValueError('Incomplete following context')
    if context.get('source_kind') not in ('synthetic_scene_request', 'native_observation'):
        raise ValueError('Unrecognized context source kind')
    if context['source_kind'] == 'native_observation' and (not context.get('native_map_sha256') or
            type(context.get('observed_frame_count')) is not int):
        raise ValueError('Native context lacks original map/frame provenance')
    rows = [json.loads(line) for line in samples_path.read_text().splitlines() if line.strip()]
    if len(rows) < MIN_FOLLOW_FRAMES:
        raise ValueError('Too few original following samples')
    if context['source_kind'] == 'native_observation' and context['observed_frame_count'] != len(rows):
        raise ValueError('Native context frame count differs from original samples')
    frames, times, gaps, headways, speeds, lead_speeds = [], [], [], [], [], []
    for row in rows:
        frame, time = row.get('native_frame'), row.get('time_s')
        if type(frame) is not int or frame < 0 or type(time) not in (int, float) or not math.isfinite(time):
            raise ValueError('Invalid original frame/time')
        if frames and (frame <= frames[-1] or time <= times[-1] or
                       abs(time-times[-1]-1/RATE_HZ) > .002):
            raise ValueError('Original frame/time order or rate invalid')
        ego, lead = row.get('ego'), row.get('lead')
        if not isinstance(ego, dict) or not isinstance(lead, dict):
            raise ValueError('Missing original ego or lead')
        if ego.get('native_road_id') != context['native_road_id'] or lead.get('native_road_id') != context['native_road_id']:
            raise ValueError('Original road identity differs')
        if ego.get('native_lane_id') != context['native_lane_id'] or lead.get('native_lane_id') != context['native_lane_id']:
            raise ValueError('Original following lane differs')
        forward = point(ego.get('native_forward_xy'), 'ego forward')
        lead_forward = point(lead.get('native_forward_xy'), 'lead forward')
        if abs(math.hypot(*forward)-1) > .01 or sum(a*b for a, b in zip(forward, lead_forward)) < .99:
            raise ValueError('Original following headings differ')
        ego_speed, lead_speed = ego.get('speed_mps'), lead.get('speed_mps')
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0
               for v in (ego_speed, lead_speed)):
            raise ValueError('Invalid original speed')
        if ego_speed < 1 or lead_speed < 1:
            raise ValueError('Lead and ego must be genuinely moving')
        rear_ego, front_ego, left_ego, right_ego = body_projections(
            ego.get('native_body_xy_m'), forward, 'ego')
        rear_lead, front_lead, left_lead, right_lead = body_projections(
            lead.get('native_body_xy_m'), forward, 'lead')
        if min(right_ego, right_lead)-max(left_ego, left_lead) <= 0:
            raise ValueError('Lead not laterally on following path')
        gap = rear_lead-front_ego
        if gap <= 0 or front_lead <= front_ego or rear_ego >= rear_lead:
            raise ValueError('Original lead not ahead with positive bumper gap')
        frames.append(frame)
        times.append(time)
        gaps.append(gap)
        headways.append(gap/ego_speed)
        speeds.append(ego_speed)
        lead_speeds.append(lead_speed)
    if len(gaps) < MIN_FOLLOW_FRAMES:
        raise ValueError('No five-second moving following interval')
    return {'format': 'c102304-moving-follow-observation-v1',
            'source_sha256': {samples_path.name: sha(samples_path),
                              context_path.name: sha(context_path)},
            'original_frames': len(rows), 'first_frame': frames[0],
            'last_frame': frames[-1], 'following_duration_s': round(len(gaps)/RATE_HZ, 5),
            'min_bumper_gap_m': round(min(gaps), 6),
            'median_bumper_gap_m': round(statistics.median(gaps), 6),
            'median_time_headway_s': round(statistics.median(headways), 6),
            'median_ego_speed_mps': round(statistics.median(speeds), 6),
            'median_lead_speed_mps': round(statistics.median(lead_speeds), 6),
            'context_status': ('native_observed_limited' if context['source_kind'] == 'native_observation'
                               else 'requested_not_observed'),
            'native_highway_status_verified': False,
            'reasonable_and_prudent_verdict_claimed': False}
