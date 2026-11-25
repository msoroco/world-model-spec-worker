"""Engineering controller for the subsection 1 stopping-reference order.

The reference comes from sourced site geometry. A commanded brake never proves
that a Native vehicle stopped in the required place; original body and velocity
samples must confirm it. No numeric speed or distance is a legal threshold.
"""

from dataclasses import dataclass
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Missing finite ' + label)
    return float(value)


def _xml_float(value, label):
    try:
        return _finite(float(value), label)
    except (TypeError, ValueError) as error:
        raise ValueError('Missing finite ' + label) from error


def select_reference(site):
    """Select line, else near crosswalk, else nearest-view point from source."""
    if not isinstance(site, dict):
        raise ValueError('Missing sourced stopping-reference geometry')
    boundary = _finite(site.get('ego_intersection_boundary_x_m'), 'intersection boundary')
    for kind in ('stop_line', 'near_crosswalk', 'nearest_view'):
        item = site.get(kind)
        if not isinstance(item, dict) or type(item.get('present')) is not bool:
            raise ValueError('Missing sourced ' + kind + ' presence')
        if item['present']:
            x = _finite(item.get('x_m'), kind + ' position')
            source = item.get('source')
            if not isinstance(source, str) or not source:
                raise ValueError('Unsourced ' + kind + ' position')
            if x >= boundary:
                raise ValueError('Stopping reference is within intersection')
            return {'kind': kind, 'x_m': x, 'source': source,
                    'intersection_boundary_x_m': boundary,
                    'legal_visibility_review_pending': kind == 'nearest_view'}
    raise ValueError('No sourced stopping reference')


def from_authored_site(path):
    """Read marked line/crosswalk and an explicit unverified view candidate."""
    path = Path(path)
    root = ET.parse(path).getroot()
    if root.tag != 'OpenDRIVE':
        raise ValueError('Stopping-reference source is not OpenDRIVE')
    road = root.find("./road[@id='158190']")
    if road is None:
        raise ValueError('Signed ego approach is absent')
    start = road.find('./planView/geometry')
    if start is None or start.find('line') is None or _xml_float(start.get('hdg'), 'road heading') != 0:
        raise ValueError('Signed approach is not the authored straight eastbound road')
    origin = _xml_float(start.get('x'), 'road origin')
    boundary = origin + _xml_float(road.get('length'), 'ego road length')
    objects = road.findall('./objects/object')
    line = [item for item in objects if item.get('type') == 'roadMark'
            and item.get('name') == 'StopLine']
    walk = [item for item in objects if item.get('type') == 'crosswalk']
    if len(line) > 1 or len(walk) > 1:
        raise ValueError('Ambiguous authored stopping reference')
    view = [item for item in road.findall('userData')
            if item.get('code') == 'nearestViewCandidateX']
    if len(view) != 1:
        raise ValueError('Missing authored nearest-view candidate')
    line_x = origin + _xml_float(line[0].get('s'), 'stop line s') if line else None
    walk_x = (origin + _xml_float(walk[0].get('s'), 'crosswalk s')
              - _xml_float(walk[0].get('width'), 'crosswalk width') / 2) if walk else None
    candidate = _xml_float(view[0].get('value'), 'nearest-view candidate')
    geometry = {'ego_intersection_boundary_x_m': boundary,
                'stop_line': {'present': bool(line), 'x_m': line_x,
                              'source': path.name + '#' + line[0].get('id') if line else None},
                'near_crosswalk': {'present': bool(walk), 'x_m': walk_x,
                                   'source': path.name + '#' + walk[0].get('id') if walk else None},
                'nearest_view': {'present': True, 'x_m': candidate,
                                 'source': path.name + '#nearestViewCandidateX'}}
    return select_reference(geometry)


@dataclass
class ApproachState:
    phase: str = 'approach'
    stopped_ticks: int = 0
    overshot_reference: bool = False


def control_step(state, *, front_x_m, speed_mps, reference, hold_ticks,
                 throttle=0.3, deceleration_mps2=3.0, margin_m=1.0):
    """Return a bounded command; flag overshoot instead of claiming success.

    `front_x_m` is the most forward original ego body x coordinate, and x grows
    toward the junction. `deceleration_mps2` and `margin_m` are engineering
    margins. Native deceleration and stop placement remain observed outcomes.
    """
    if not isinstance(state, ApproachState) or state.phase not in {
            'approach', 'braking', 'holding', 'proceed', 'overshot'}:
        raise ValueError('Invalid approach controller state')
    front = _finite(front_x_m, 'ego front x')
    speed = _finite(speed_mps, 'ego speed')
    if speed < 0:
        raise ValueError('Negative ego speed')
    target = _finite(reference.get('x_m') if isinstance(reference, dict) else None,
                     'selected stopping reference')
    if type(hold_ticks) is not int or hold_ticks < 1:
        raise ValueError('Positive engineering hold ticks required')
    if not 0 < _finite(throttle, 'throttle') <= 1:
        raise ValueError('Invalid throttle')
    if _finite(deceleration_mps2, 'deceleration') <= 0 or _finite(margin_m, 'margin') < 0:
        raise ValueError('Invalid braking engineering values')
    if state.phase not in {'proceed', 'overshot'} and front > target:
        state.phase, state.overshot_reference = 'overshot', True
    if state.phase == 'overshot':
        return {'throttle': 0.0, 'brake': 1.0, 'phase': 'overshot',
                'engineering_hold_reached': False}
    if state.phase == 'proceed':
        return {'throttle': float(throttle), 'brake': 0.0, 'phase': 'proceed',
                'engineering_hold_reached': True}
    braking_distance = speed * speed / (2 * deceleration_mps2) + margin_m
    if state.phase == 'approach' and target - front <= braking_distance:
        state.phase = 'braking'
    if state.phase == 'approach':
        return {'throttle': float(throttle), 'brake': 0.0, 'phase': 'approach',
                'engineering_hold_reached': False}
    if speed > 0.05:
        return {'throttle': 0.0, 'brake': 1.0, 'phase': 'braking',
                'engineering_hold_reached': False}
    state.phase = 'holding'
    state.stopped_ticks += 1
    if state.stopped_ticks < hold_ticks:
        return {'throttle': 0.0, 'brake': 1.0, 'phase': 'holding',
                'engineering_hold_reached': False}
    state.phase = 'proceed'
    return {'throttle': float(throttle), 'brake': 0.0, 'phase': 'proceed',
            'engineering_hold_reached': True}
