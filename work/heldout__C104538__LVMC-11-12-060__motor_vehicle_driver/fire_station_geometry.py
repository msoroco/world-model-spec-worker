"""Source-bound fire-station entrance geometry for Native construction.

The caller must identify a real fire-station asset and the public-road/driveway
lane pair in the local map survey. This module rejects a merely labelled U-turn.
It does not establish that the surveyed asset is a fire station.
"""

from dataclasses import dataclass
from math import atan2, cos, hypot, pi, sin


@dataclass(frozen=True)
class Point:
    x: float
    y: float


def _point(location):
    return Point(float(location.x), float(location.y))


def _heading(a, b):
    return atan2(b.y - a.y, b.x - a.x)


def _wrap(angle):
    return atan2(sin(angle), cos(angle))


def _lane_identity(waypoint):
    return (waypoint.road_id, waypoint.lane_id)


def validate_entrance(public_before, public_at, public_after, driveway_at, *,
                      source, min_branch_angle_deg=35):
    """Validate measured map geometry; return a reproducible local reference.

    All waypoints are original map waypoints chosen by a survey, not inferred
    from legal labels. A driveway must be a distinct lane diverging from the
    public lane near its entrance. The source binds a map landmark or survey.
    """
    if not isinstance(source, dict) or source.get('kind') not in ('map_landmark', 'operator_survey'):
        raise ValueError('source-bound fire-station identification required')
    if not source.get('asset_id') or not source.get('source_sha256'):
        raise ValueError('fire-station source asset and hash required')
    if len(source['source_sha256']) != 64:
        raise ValueError('fire-station source SHA256 malformed')
    if _lane_identity(public_before) != _lane_identity(public_at) or _lane_identity(public_after) != _lane_identity(public_at):
        raise ValueError('public approach is not one continuous lane')
    if _lane_identity(driveway_at) == _lane_identity(public_at):
        raise ValueError('driveway is not a separate lane')
    before = _point(public_before.transform.location)
    at = _point(public_at.transform.location)
    after = _point(public_after.transform.location)
    driveway = _point(driveway_at.transform.location)
    if not 2.0 <= hypot(after.x - before.x, after.y - before.y) <= 40.0:
        raise ValueError('public approach sample spacing invalid')
    if hypot(driveway.x - at.x, driveway.y - at.y) > 12.0:
        raise ValueError('driveway is too far from public entrance')
    public_heading = _heading(before, after)
    driveway_heading = _heading(at, driveway)
    branch_angle = abs(_wrap(driveway_heading - public_heading)) * 180 / pi
    if branch_angle < min_branch_angle_deg:
        raise ValueError('driveway lacks a physical branch angle')
    return {
        'source': dict(source),
        'public_lane': _lane_identity(public_at),
        'driveway_lane': _lane_identity(driveway_at),
        'entrance_xy_m': [at.x, at.y],
        'public_heading_rad': public_heading,
        'driveway_heading_rad': driveway_heading,
        'branch_angle_deg': branch_angle,
    }


def classify_path(samples, geometry, *, entrance_radius_m=5.0):
    """Describe realized center path without assigning a legal conclusion.

    Samples contain original-frame position and heading. A reversal requires
    observed motion on both sides of the episode; a driveway visit requires
    a measured position on its distinct mapped lane.
    """
    if len(samples) < 3:
        raise ValueError('original path has fewer than three samples')
    frames = [s['frame'] for s in samples]
    if frames != sorted(set(frames)):
        raise ValueError('original frame identities are not unique and increasing')
    x0, y0 = geometry['entrance_xy_m']
    near = [s['frame'] for s in samples if hypot(s['x_m'] - x0, s['y_m'] - y0) <= entrance_radius_m]
    driveway = [s['frame'] for s in samples if tuple(s['lane_id']) == tuple(geometry['driveway_lane'])]
    delta = abs(_wrap(samples[-1]['heading_rad'] - samples[0]['heading_rad'])) * 180 / pi
    return {
        'heading_change_deg': delta,
        'reversal_observed': delta >= 150.0,
        'near_entrance_frames': near,
        'driveway_frames': driveway,
        'entered_driveway': bool(driveway),
        'in_front_of_entrance_observed': bool(near),
        'purpose_of_turning': 'unresolved_contextual_judgment',
        'physical_fire_station_identity': 'unresolved_until_source_review',
    }
