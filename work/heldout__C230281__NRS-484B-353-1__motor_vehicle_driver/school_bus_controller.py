"""Construction control targets for the eight selected school-bus cases."""
from __future__ import annotations
import math

BRANCHES = {
    'meeting_stop', 'meeting_restart_before_red_ceases', 'meeting_pass_red',
    'overtaking_stop', 'overtaking_pass_red',
    'meeting_divided_other_roadway_pass', 'meeting_officer_controlled_pass',
    'meeting_resume_after_red_ceases',
}
PASS_DURING_RED = {
    'meeting_pass_red', 'overtaking_pass_red',
    'meeting_divided_other_roadway_pass', 'meeting_officer_controlled_pass',
}


def target(branch, *, red_signal_operating, stop_observed):
    """Prescribe scenario motion; source measurements decide what occurred."""
    if branch not in BRANCHES or type(red_signal_operating) is not bool or type(stop_observed) is not bool:
        raise ValueError('Unknown school-bus branch or signal/stop state')
    if branch == 'meeting_restart_before_red_ceases':
        speed = 5.0 if (stop_observed or not red_signal_operating) else 0.0
    elif branch in PASS_DURING_RED or not red_signal_operating:
        speed = 5.0
    else:
        speed = 0.0
    return {'branch': branch, 'target_speed_mps': speed,
            'red_signal_operating': red_signal_operating,
            'construction_only': True, 'legal_conclusion': None}


def apply(vehicle, control_type, command, *, speed_mps):
    if (not isinstance(command, dict) or command.get('branch') not in BRANCHES or
        type(speed_mps) not in (int, float) or speed_mps < 0):
        raise ValueError('Invalid school-bus vehicle/control state')
    error = command['target_speed_mps'] - speed_mps
    throttle = min(0.65, max(0.0, 0.20*error))
    brake = min(1.0, max(0.0, -0.35*error))
    output = control_type(throttle=throttle, brake=brake, steer=0.0)
    vehicle.apply_control(output)
    return output


def motion_readback(subject, bus, travel_tangent_xy, frame, time_s):
    """Read actual actor bounds and velocity for the original motion source."""
    if (not isinstance(travel_tangent_xy, (tuple, list)) or len(travel_tangent_xy) != 2 or
        any(type(v) not in (int, float) or not math.isfinite(v) for v in travel_tangent_xy) or
        abs(math.hypot(*travel_tangent_xy) - 1) > .01 or
        type(frame) is not int or frame < 0 or
        type(time_s) not in (int, float) or not math.isfinite(time_s) or time_s < 0):
        raise ValueError('Native school-bus frame/tangent invalid')
    def corners(actor):
        transform = actor.get_transform()
        vertices = list(actor.bounding_box.get_world_vertices(transform))
        if len(vertices) != 8:
            raise ValueError('Native school-bus body vertices missing')
        lower = sorted(vertices, key=lambda vertex: vertex.z)[:4]
        result = [[float(vertex.x), float(vertex.y)] for vertex in lower]
        if any(not math.isfinite(value) for pair in result for value in pair):
            raise ValueError('Native school-bus body vertices nonfinite')
        return result
    velocity = subject.get_velocity()
    speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
    if not math.isfinite(speed):
        raise ValueError('Native school-bus velocity nonfinite')
    return {'frame': frame, 'time_s': float(time_s), 'subject_id': str(subject.id),
            'bus_id': str(bus.id), 'subject_speed_mps': speed,
            'subject_corners': corners(subject), 'bus_corners': corners(bus),
            'travel_tangent_xy': [float(value) for value in travel_tangent_xy]}


def spawn_meeting_scene(world, carla_module, scene):
    """Create the bus and oncoming subject on one original undivided road.

    Bus qualification, legally required equipment, pupil purpose, and actual
    front/rear lamp visibility remain separate source/audit requirements.
    """
    if (not isinstance(scene, dict) or not scene.get('bus_blueprint_id') or
        not scene.get('subject_blueprint_id') or not scene.get('bus_transform') or
        not scene.get('subject_transform')):
        raise ValueError('Missing school-bus actor construction parameters')
    bus_transform = scene['bus_transform']
    subject_transform = scene['subject_transform']
    mapping = world.get_map()
    bus_waypoint = mapping.get_waypoint(bus_transform.location)
    subject_waypoint = mapping.get_waypoint(subject_transform.location)
    if bus_waypoint is None or subject_waypoint is None or (
        bus_waypoint.road_id != subject_waypoint.road_id or
        bus_waypoint.is_junction or subject_waypoint.is_junction):
        raise ValueError('Meeting scene requires one nonjunction road')
    a = bus_waypoint.transform.get_forward_vector()
    b = subject_waypoint.transform.get_forward_vector()
    dot = a.x*b.x + a.y*b.y
    if not math.isfinite(dot) or dot > -.8:
        raise ValueError('Meeting scene requires opposite travel directions')
    blueprints = world.get_blueprint_library()
    bus_bp = blueprints.find(scene['bus_blueprint_id'])
    subject_bp = blueprints.find(scene['subject_blueprint_id'])
    bus = world.try_spawn_actor(bus_bp, bus_transform)
    if bus is None:
        raise ValueError('Native school-bus spawn failed')
    try:
        subject = world.try_spawn_actor(subject_bp, subject_transform)
        if subject is None:
            raise ValueError('Native meeting subject spawn failed')
        bus.apply_control(carla_module.VehicleControl(throttle=0, brake=1,
                                                      hand_brake=True))
        return {'bus': bus, 'subject': subject, 'bus_waypoint': bus_waypoint,
                'subject_waypoint': subject_waypoint,
                'road_id': bus_waypoint.road_id, 'heading_dot': dot,
                'bus_equipment_verified': False,
                'pupil_purpose_verified': False,
                'red_visibility_verified': False}
    except BaseException:
        bus.destroy()
        raise
