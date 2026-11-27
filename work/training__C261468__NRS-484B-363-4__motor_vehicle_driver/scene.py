"""Survey-gated construction of the two vehicles for C261468.

The survey is a local Native input. A CPU fixture can test its validation and
spawn calls, but cannot establish original sign authority or physical success.
"""

import hashlib
import json
import math
import re
from pathlib import Path

ASSIGNMENT = 'training__C261468__NRS-484B-363-4__motor_vehicle_driver'
CASE_PLAN = Path(__file__).resolve().with_name('case-plan.json')
if not CASE_PLAN.is_file():
    CASE_PLAN = Path(__file__).resolve().parents[1] / 'case-plan.json'


def _finite_tuple(value, length):
    return isinstance(value, list) and len(value) == length and all(
        type(item) in (int, float) and math.isfinite(item) for item in value)


def _source(survey, name):
    item = survey.get(name)
    if (not isinstance(item, dict) or not item.get('path') or
            not isinstance(item.get('sha256'), str) or
            re.fullmatch(r'[0-9a-f]{64}', item['sha256']) is None):
        raise ValueError('Missing reviewed source receipt: ' + name)
    root = survey.get('source_root')
    if not isinstance(root, str) or not root:
        raise ValueError('Survey source root missing')
    root_path = Path(root).resolve()
    source_path = (root_path / item['path']).resolve()
    if (not source_path.is_relative_to(root_path) or not source_path.is_file() or
            hashlib.sha256(source_path.read_bytes()).hexdigest() != item['sha256']):
        raise ValueError('Reviewed source bytes differ or are missing: ' + name)


def validate_survey(survey):
    """Reject a plan that cannot bind the same-direction pass and installed device."""
    cases = {row['case_id']: row for row in json.loads(CASE_PLAN.read_text())['cases']}
    case_id = survey.get('case_id')
    if case_id not in cases or survey.get('assignment_id') != ASSIGNMENT:
        raise ValueError('Survey does not bind an exact planned case')
    if not survey.get('map_name') or not survey.get('road_id'):
        raise ValueError('Surveyed map and road are required')
    axis = survey.get('road_axis_xy')
    if not _finite_tuple(axis, 2) or abs(math.hypot(*axis) - 1) > .01:
        raise ValueError('Surveyed route axis must be unit length')
    bounds = survey.get('zone_station_bounds_m')
    if not _finite_tuple(bounds, 2) or bounds[0] >= bounds[1]:
        raise ValueError('Surveyed school-zone boundaries invalid')
    for name in ('ego', 'other'):
        actor = survey.get(name)
        if (not isinstance(actor, dict) or not isinstance(actor.get('blueprint'), str) or
                not actor['blueprint'].startswith('vehicle.') or
                not _finite_tuple(actor.get('xyz_m'), 3) or
                type(actor.get('yaw_deg')) not in (int, float) or
                not math.isfinite(actor['yaw_deg'])):
            raise ValueError('Surveyed vehicle blueprint or transform missing: ' + name)
    ego, other = survey['ego'], survey['other']
    if abs(((ego['yaw_deg'] - other['yaw_deg'] + 180) % 360) - 180) > 5:
        raise ValueError('Overtaken vehicle does not share the route direction')
    for name, actor in (('ego', ego), ('other', other)):
        yaw = math.radians(actor['yaw_deg'])
        if math.cos(yaw) * axis[0] + math.sin(yaw) * axis[1] < .99:
            raise ValueError('Surveyed vehicle faces against route axis: ' + name)
    def station(actor):
        return actor['xyz_m'][0] * axis[0] + actor['xyz_m'][1] * axis[1]
    if not (bounds[0] < station(ego) < station(other) < bounds[1]):
        raise ValueError('Subject must start behind other vehicle within signed zone')
    planned = cases[case_id].get('requested_context', {})
    if survey.get('planned_context') != planned:
        raise ValueError('Reviewed condition differs from exact case plan')
    if survey.get('zone_kind') != planned.get('zone_kind'):
        raise ValueError('Installed zone kind differs from exact case')
    for key in ('calendar', 'operation_hours', 'civil_time', 'zone_designation',
                'zone_boundary', 'installed_sign', 'pass_route'):
        _source(survey, key + '_source')
    sign = survey.get('installed_sign')
    if (not isinstance(sign, dict) or type(sign.get('actor_id')) is not int or
            not sign.get('asset_id') or not _finite_tuple(sign.get('xyz_m'), 3) or
            sign.get('zone_kind') != survey['zone_kind']):
        raise ValueError('Installed zone sign actor is not identified')
    if planned.get('beacon_operational'):
        _source(survey, 'beacon_controller_source')
        beacon = survey.get('beacon')
        if (not isinstance(beacon, dict) or beacon.get('sign_actor_id') != sign['actor_id'] or
                not isinstance(beacon.get('yellow_lights'), list) or
                len(beacon['yellow_lights']) < 2):
            raise ValueError('Operational sign beacon needs two yellow lights')
        ids = []
        for lamp in beacon['yellow_lights']:
            if (not isinstance(lamp, dict) or type(lamp.get('actor_id')) is not int or
                    not lamp.get('asset_id') or lamp.get('color') != 'yellow' or
                    not _finite_tuple(lamp.get('xyz_m'), 3) or
                    math.dist(lamp['xyz_m'], sign['xyz_m']) > 5):
                raise ValueError('Beacon yellow lamp actor is not source-identified')
            ids.append(lamp['actor_id'])
        if len(set(ids)) != len(ids):
            raise ValueError('Beacon yellow lamp actors must be distinct')
    elif survey.get('beacon') is not None:
        raise ValueError('Nonbeacon case cannot claim an installed operational beacon')
    return case_id


def verify_installed_devices(world, carla, survey):
    """Check actor IDs, asset IDs and surveyed positions against live CARLA actors."""
    devices = [survey['installed_sign']]
    if survey.get('beacon'):
        devices.extend(survey['beacon']['yellow_lights'])
    for device in devices:
        actor = world.get_actors().find(device['actor_id'])
        if (actor is None or actor.type_id != device['asset_id'] or
                actor.get_location().distance(carla.Location(
                    x=device['xyz_m'][0], y=device['xyz_m'][1], z=device['xyz_m'][2])) > .5):
            raise ValueError('Live installed sign or beacon actor differs from survey')


def spawn_pass_pair(world, carla, survey):
    """Spawn the surveyed subject and overtaken vehicle; caller owns cleanup."""
    validate_survey(survey)
    if world.get_map().name != survey['map_name']:
        raise ValueError('Live map differs from surveyed school zone')
    verify_installed_devices(world, carla, survey)
    spawned = []
    try:
        for name in ('ego', 'other'):
            spec = survey[name]
            blueprint = world.get_blueprint_library().find(spec['blueprint'])
            location = carla.Location(x=spec['xyz_m'][0], y=spec['xyz_m'][1], z=spec['xyz_m'][2])
            transform = carla.Transform(location, carla.Rotation(yaw=spec['yaw_deg']))
            actor = world.try_spawn_actor(blueprint, transform)
            if actor is None:
                raise ValueError('Surveyed vehicle spawn failed: ' + name)
            spawned.append(actor)
        return tuple(spawned)
    except Exception:
        for actor in reversed(spawned):
            actor.destroy()
        raise
