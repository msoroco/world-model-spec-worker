"""Derive fire-lane stop geometry from retained actor and live-survey sources.

The authored polygon is a comparison target. Neither it nor the sign actor ID
proves City Fire Code designation, posting text, or actual pixel visibility.
"""
import hashlib
import json
from math import hypot, isfinite
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon

from fire_lane_survey import require


KINDS = {'original_carla_actor_and_map_readback', 'synthetic_native_sample'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_lines(path):
    require(path.is_file(), 'Missing retained source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def vector(value, length):
    return isinstance(value, list) and len(value) == length and all(
        type(x) in (int, float) and isfinite(x) for x in value)


def analyze(attempt, case, *, diagnostic=False):
    attempt = Path(attempt)
    require(case in ('reference', 'contrast'), 'Unknown fire-lane case')
    plan_path = attempt / 'native-survey-readback.json'
    require(plan_path.is_file(), 'Missing live survey readback')
    plan = json.loads(plan_path.read_text())
    require(plan.get('format') == 'c201084-fire-lane-construction-plan-v1' and
            plan.get('cell_id') == 'C201084' and
            plan.get('posting_designation_verified') is False and
            plan.get('original_sign_text_verified') is False,
            'Survey readback has invalid identity or posting claim')
    kind = 'synthetic_native_sample' if diagnostic else 'original_carla_actor_and_map_readback'
    require(kind in KINDS and
            plan['cases'][case]['road_readback'].get('source_kind') ==
                ('synthetic_construction_probe' if diagnostic else 'original_carla_map_readback'),
            'Survey road provenance differs')
    sign = plan.get('sign_readback')
    require(isinstance(sign, dict) and
            sign.get('actor_id') == plan['fixed_context']['posted_sign_actor_id'] and
            sign.get('source_kind') ==
                ('synthetic_native_sample' if diagnostic else 'original_carla_actor_readback'),
            'Sign actor readback provenance differs')
    zone = Polygon(plan['survey_geometry']['authored_fire_lane_polygon_xy_m'])
    require(zone.is_valid and zone.area > 0, 'Surveyed fire-lane geometry invalid')
    actor_path = attempt/'native-actors.jsonl'
    frame_path = attempt/'video_frames.jsonl'
    actors = read_lines(actor_path)
    frames = read_lines(frame_path)
    require(len(actors) == len(frames) and len(actors) >= 2,
            'Native actor/frame source join incomplete')
    if not diagnostic:
        require(len(actors) >= plan['capture_frames'] >= 600,
                'Original capture shorter than thirty seconds')
    observed_actor = None
    observed_follower = None
    samples = []
    for index, (actor, frame) in enumerate(zip(actors, frames)):
        require(type(actor.get('frame')) is int and
                actor['frame'] == frame.get('carla_frame') and
                frame.get('video_frame') == index and
                type(frame.get('time_s')) in (int, float) and
                isfinite(frame['time_s']) and
                abs(frame['time_s'] - index/20) < 1e-4,
                'Original actor/video frame join differs')
        require(actor.get('source_kind') == kind and
                type(actor.get('ego_actor_id')) is int and
                actor.get('driving_road_id') == plan['fixed_context']['road_id'] and
                actor.get('following_road_id') == plan['fixed_context']['road_id'] and
                actor.get('sign_actor_id') == sign['actor_id'],
                'Actor, road or sign source identity differs')
        if observed_actor is None:
            observed_actor = actor['ego_actor_id']
        if observed_follower is None:
            observed_follower = actor.get('following_actor_id')
        require(actor['ego_actor_id'] == observed_actor and
                type(observed_follower) is int and
                observed_follower != observed_actor and
                actor.get('following_actor_id') == observed_follower and
                vector(actor.get('ego_velocity_xyz_mps'), 3) and
                vector(actor.get('following_velocity_xyz_mps'), 3) and
                isinstance(actor.get('ego_body_vertices_xyz_m'), list) and
                len(actor['ego_body_vertices_xyz_m']) >= 4 and
                all(vector(v, 3) for v in actor['ego_body_vertices_xyz_m']) and
                isinstance(actor.get('following_body_vertices_xyz_m'), list) and
                len(actor['following_body_vertices_xyz_m']) >= 4 and
                all(vector(v, 3) for v in actor['following_body_vertices_xyz_m']) and
                type(actor.get('following_gap_m')) in (int, float) and
                isfinite(actor['following_gap_m']) and actor['following_gap_m'] >= 0,
                'Original ego motion or body source incomplete')
        body = MultiPoint([(v[0], v[1]) for v in
                           actor['ego_body_vertices_xyz_m']]).convex_hull
        require(body.geom_type == 'Polygon' and body.area > 0,
                'Original body footprint invalid')
        vx, vy, vz = actor['ego_velocity_xyz_mps']
        speed = hypot(hypot(vx, vy), vz)
        fx, fy, fz = actor['following_velocity_xyz_mps']
        following_speed = hypot(hypot(fx, fy), fz)
        samples.append({'carla_frame': actor['frame'], 'time_s': frame['time_s'],
                        'speed_mps': speed,
                        'following_speed_mps': following_speed,
                        'following_gap_m': actor['following_gap_m'],
                        'body_zone_overlap_m2': body.intersection(zone).area,
                        'body_fully_in_authored_zone': zone.covers(body),
                        'body_disjoint_from_authored_zone': zone.disjoint(body)})
    return {'format': 'c201084-source-stop-measurement-v1',
            'case': case, 'source_kind': kind, 'ego_actor_id': observed_actor,
            'frames': len(samples), 'actor_source_sha256': sha(actor_path),
            'frame_map_sha256': sha(frame_path),
            'survey_readback_sha256': sha(plan_path),
            'samples': samples,
            'near_zero_motion_sample_tolerance_mps': 0.05,
            'near_zero_with_zone_overlap_frames': sum(
                s['speed_mps'] <= 0.05 and s['body_zone_overlap_m2'] > 0
                for s in samples),
            'near_zero_disjoint_frames': sum(
                s['speed_mps'] <= 0.05 and s['body_disjoint_from_authored_zone']
                for s in samples),
            'actual_sign_text_verified': False,
            'fire_code_designation_verified': False,
            'physical_or_legal_completion_claimed': False}
