"""Native acquisition helpers for exact crosswalk qualification variants.

The helpers record actor and device state. Their presence never decides whether
the statutory exception applies; authority and necessity are reviewed later.
"""
import json


QUALIFIERS = {
    'traffic_conflict_near': 'traffic_conflict',
    'law_compliance_near': 'law_compliance',
    'police_direction_near': 'police_direction',
    'device_direction_near': 'device_direction',
}


def spawn_traffic_actor(world, carla, owned):
    blueprints = sorted(world.get_blueprint_library().filter('vehicle.*'), key=lambda item: item.id)
    if len(blueprints) < 2:
        raise RuntimeError('Second Native traffic vehicle blueprint unavailable')
    blueprint = blueprints[1]
    blueprint.set_attribute('role_name', 'c229397_traffic_context')
    actor = world.spawn_actor(blueprint, carla.Transform(
        carla.Location(x=-16.0, y=-1.75, z=8.8), carla.Rotation(yaw=0)))
    owned.append(actor)
    return actor


def traffic_command(actor, index, carla):
    command = {'throttle': .18 if index < 260 else 0.0,
               'brake': 0.0 if index < 260 else .7, 'hand_brake': False}
    actor.apply_control(carla.VehicleControl(**command, steer=0))
    return command


def traffic_row(actor, index, native_frame, elapsed, command):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    extent = actor.bounding_box.extent
    return {'video_frame': index, 'native_frame': native_frame, 'time_s': elapsed,
            'actor_id': actor.id, 'blueprint_id': actor.type_id,
            'vehicle_xy_m': [transform.location.x, transform.location.y],
            'yaw_deg': transform.rotation.yaw,
            'bbox_half_length_m': extent.x, 'bbox_half_width_m': extent.y,
            'speed_mps': (velocity.x**2 + velocity.y**2 + velocity.z**2)**.5,
            'applied_control': command}


def find_device(world):
    actors = [actor for actor in world.get_actors().filter('traffic.traffic_light*')]
    near = [actor for actor in actors if
            -12 <= actor.get_transform().location.x <= 12 and
            -10 <= actor.get_transform().location.y <= 4]
    return sorted(near, key=lambda actor: actor.id)[0] if near else None


def device_row(device, index, native_frame, elapsed):
    if device is None:
        return {'video_frame': index, 'native_frame': native_frame, 'time_s': elapsed,
                'device_present': False, 'device_id': None, 'state': None,
                'source_status': 'Native device unavailable; direction unresolved'}
    transform = device.get_transform()
    return {'video_frame': index, 'native_frame': native_frame, 'time_s': elapsed,
            'device_present': True, 'device_id': device.id,
            'type_id': device.type_id, 'state': str(device.get_state()),
            'location_xyz_m': [transform.location.x, transform.location.y, transform.location.z],
            'source_status': 'Native device state only; authority and applicability unresolved'}


def write_context_manifest(path, case, device):
    value = {'format': 'c229397-native-qualifier-context-v1', 'qualifier': QUALIFIERS[case],
             'case_suffix': case, 'traffic_actor_requested': case == 'traffic_conflict_near',
             'device_requested': case == 'device_direction_near',
             'device_actor_found': device is not None,
             'authority_and_necessity_unresolved': True,
             'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    path.write_text(json.dumps(value, indent=2) + '\n')
    return value
