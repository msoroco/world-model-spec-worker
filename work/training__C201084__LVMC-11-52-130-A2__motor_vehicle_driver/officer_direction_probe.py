"""Retain an original pedestrian actor for the draft officer-direction route.

CARLA pedestrian identity and pose cannot establish police authority or an
instruction to this driver. Those judgments require independent source review.
"""
from math import hypot, isfinite

from fire_lane_survey import require


def inspect_officer(world, survey):
    requested = survey.get('police_officer')
    require(isinstance(requested, dict), 'Officer survey missing')
    actor_id = requested.get('actor_id')
    xy = requested.get('position_xy_m')
    require(type(actor_id) is int and actor_id > 0 and isinstance(xy, list) and
            len(xy) == 2 and all(type(v) in (int, float) and isfinite(v)
                                 for v in xy), 'Officer survey identity or position invalid')
    actor = world.get_actors().find(actor_id)
    require(actor is not None and actor.type_id.startswith('walker.pedestrian.'),
            'Surveyed original pedestrian actor missing')
    loc = actor.get_transform().location
    require(hypot(loc.x-xy[0], loc.y-xy[1]) <= 0.5,
            'Surveyed pedestrian moved from position')
    return {'actor_id': actor_id, 'type_id': actor.type_id,
            'position_xy_m': [loc.x, loc.y],
            'source_kind': 'original_carla_actor_readback',
            'police_authority_verified': False,
            'direction_applicability_verified': False,
            'statutory_necessity_verified': False}


def sample_officer(actor, readback, frame):
    require(type(frame) is int and frame >= 0, 'Original frame invalid')
    require(actor.id == readback['actor_id'] and actor.type_id == readback['type_id'],
            'Original pedestrian actor identity changed')
    transform = actor.get_transform()
    loc = transform.location
    require(hypot(loc.x-readback['position_xy_m'][0],
                  loc.y-readback['position_xy_m'][1]) <= 2.0,
            'Original pedestrian departed surveyed position')
    rotation = transform.rotation
    velocity = actor.get_velocity()
    values = (loc.x, loc.y, loc.z, rotation.yaw,
              velocity.x, velocity.y, velocity.z)
    require(all(isfinite(v) for v in values), 'Original pedestrian sample invalid')
    return {'frame': frame, 'officer_actor_id': actor.id,
            'officer_type_id': actor.type_id,
            'pose_xyz_yaw_deg': [loc.x, loc.y, loc.z, rotation.yaw],
            'velocity_xyz_mps': [velocity.x, velocity.y, velocity.z],
            'source_kind': 'original_carla_actor_readback',
            'police_authority_verified': False,
            'direction_applicability_verified': False,
            'statutory_necessity_verified': False}


def check_saved_officer_rows(rows, frame_rows, readback, *,
                             source_kind='original_carla_actor_readback'):
    require(len(rows) == len(frame_rows) and len(rows) >= 600,
            'Officer source must cover the full thirty-second capture')
    frames = [row['frame'] for row in frame_rows]
    require(all(type(v) is int for v in frames) and frames == sorted(set(frames)),
            'Video frame map invalid')
    for index, (row, frame) in enumerate(zip(rows, frames)):
        pose = row.get('pose_xyz_yaw_deg')
        velocity = row.get('velocity_xyz_mps')
        require(row.get('frame') == frame and row.get('video_frame') == index and
                row.get('officer_actor_id') == readback['actor_id'] and
                row.get('officer_type_id') == readback['type_id'] and
                row.get('source_kind') == source_kind and
                isinstance(pose, list) and len(pose) == 4 and
                isinstance(velocity, list) and len(velocity) == 3 and
                all(type(v) in (int, float) and isfinite(v)
                    for v in pose + velocity) and
                row.get('police_authority_verified') is False and
                row.get('direction_applicability_verified') is False and
                row.get('statutory_necessity_verified') is False,
                'Saved officer source differs or overclaims')
    return {'source_frames': len(rows), 'officer_actor_id': readback['actor_id'],
            'police_authority_verified': False,
            'direction_applicability_verified': False,
            'statutory_necessity_verified': False}
