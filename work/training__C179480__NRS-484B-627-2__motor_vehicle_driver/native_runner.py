"""Survey-driven Native attempt entrypoint for C179480 roadway-stop scenes.

This program never supplies a map identity or shoulder from an invented fixture.
An operator must provide a surveyed CARLA lane and the runner checks it against
the live map before spawning either participant. Capture remains unfinalized.
"""
import argparse
import hashlib
import json
from math import cos, radians, sin
from pathlib import Path

from capture_attempt import acquire_with_world_restore
from candidate_tuning import TUNINGS, tuning
from source_measurement import analyze, analyze_hazard
from stop_construction import RoadProfile, target


CASES = {'reference': True, 'contrast': False, 'safe_operation_stop': True}


def validate_survey(survey, mapping, carla):
    required = {'map_name', 'anchor', 'lane_width_m', 'shoulder_width_m',
                'vehicle_width_m', 'ego_blueprint', 'following_blueprint',
                'frames'}
    if not required <= set(survey):
        raise ValueError('Survey lacks required map, actor or capture field')
    if mapping.name != survey['map_name']:
        raise ValueError('Live map differs from surveyed map')
    anchor = survey['anchor']
    if not {'x', 'y', 'z', 'yaw'} <= set(anchor):
        raise ValueError('Survey lacks complete anchor pose')
    road = RoadProfile(survey['lane_width_m'], survey['shoulder_width_m'],
                       survey['vehicle_width_m'])
    road.validate()
    position = carla.Location(x=anchor['x'], y=anchor['y'], z=anchor['z'])
    lane = mapping.get_waypoint(position, project_to_road=False,
                                lane_type=carla.LaneType.Driving)
    if lane is None or lane.lane_width <= 0:
        raise ValueError('Survey anchor is not on a live driving lane')
    if abs(lane.lane_width - road.lane_width_m) > 0.15:
        raise ValueError('Live driving lane width differs from survey')
    yaw_error = (anchor['yaw'] - lane.transform.rotation.yaw + 180.0) % 360.0 - 180.0
    if abs(yaw_error) > 10.0:
        raise ValueError('Survey heading differs from live lane direction')
    shoulder = lane.get_right_lane()
    if (shoulder is None or shoulder.lane_type != carla.LaneType.Shoulder
            or abs(shoulder.lane_width - road.shoulder_width_m) > 0.15):
        raise ValueError('Live right shoulder differs from survey')
    if type(survey['frames']) is not int or survey['frames'] < 2:
        raise ValueError('Survey capture duration is invalid')
    return road, lane, shoulder


def placement(survey, road, carla, case, candidate='primary'):
    if case not in CASES:
        raise ValueError('Unsupported roadway-stop scene')
    anchor = survey['anchor']
    selected = tuning(candidate)
    yaw = radians(anchor['yaw'])
    forward = (cos(yaw), sin(yaw))
    right = (-sin(yaw), cos(yaw))
    lateral = target(road, CASES[case])['ego_stop_lateral_m']
    def xy(longitudinal, lateral_offset):
        return (anchor['x'] + longitudinal*forward[0] + lateral_offset*right[0],
                anchor['y'] + longitudinal*forward[1] + lateral_offset*right[1])
    def transform(longitudinal, lateral_offset):
        x, y = xy(longitudinal, lateral_offset)
        return carla.Transform(carla.Location(x=x, y=y, z=anchor['z']+0.25),
                               carla.Rotation(yaw=anchor['yaw']))
    return {'ego_spawn': transform(selected.ego_spawn_longitudinal_m, 0.0),
            'following_spawn': transform(selected.follower_spawn_longitudinal_m, 0.0),
            'stop_xy': xy(0.0, lateral),
            'hazard_spawn': (transform(8.0, 0.0)
                             if case == 'safe_operation_stop' else None),
            'target_lane_overlap': CASES[case],
            'ego_lateral_stop_m': lateral,
            'candidate_id': candidate,
            'tuning': selected}


def run(client, carla, survey, attempt, case, *, candidate='primary', sink_factory=None):
    world = client.get_world()
    road, lane, shoulder = validate_survey(survey, world.get_map(), carla)
    plan = placement(survey, road, carla, case, candidate)
    if case == 'safe_operation_stop' and not survey.get('hazard_blueprint'):
        raise ValueError('Safe-operation scene requires surveyed hazard blueprint')
    library = world.get_blueprint_library()
    actors = []
    try:
        spawns = [
            (survey['ego_blueprint'], plan['ego_spawn']),
            (survey['following_blueprint'], plan['following_spawn'])]
        if plan['hazard_spawn'] is not None:
            spawns.append((survey['hazard_blueprint'],plan['hazard_spawn']))
        for blueprint_name, transform in spawns:
            blueprint = library.find(blueprint_name)
            actor = world.try_spawn_actor(blueprint, transform)
            if actor is None:
                raise ValueError('Surveyed vehicle spawn is occupied: '+blueprint_name)
            actors.append(actor)
        options = {'frames': survey['frames'],
                   'stop_radius_m': plan['tuning'].stop_radius_m,
                   'approach_speed_mps': plan['tuning'].approach_speed_mps,
                   'follower_brake_gap_m': plan['tuning'].follower_brake_gap_m}
        if sink_factory is not None:
            options['sink_factory'] = sink_factory
        if plan['hazard_spawn'] is not None:
            options['hazard'] = actors[2]
        receipt = acquire_with_world_restore(
            world, carla, actors[0], actors[1], library,
            plan['stop_xy'], attempt, **options)
        readback = {
            'format': 'c179480-original-map-readback-v1',
            'map_name': world.get_map().name,
            'road_id': lane.road_id, 'lane_id': lane.lane_id,
            'driving_lane_width_m': lane.lane_width,
            'driving_lane_yaw_deg': lane.transform.rotation.yaw,
            'right_shoulder_width_m': shoulder.lane_width,
            'case': case, 'planned_lane_overlap': plan['target_lane_overlap'],
            'candidate_id': candidate,
            'candidate_risk_trigger': plan['tuning'].risk_trigger,
            'ego_lateral_stop_m': plan['ego_lateral_stop_m'],
            'planned_stop_xy_m': plan['stop_xy'],
            'planned_hazard_xy_m': ([plan['hazard_spawn'].location.x,
                                     plan['hazard_spawn'].location.y]
                                    if plan['hazard_spawn'] is not None else None),
            'physical_completion_claimed': False,
        }
        (Path(attempt) / 'native-map-readback.json').write_text(
            json.dumps(readback, indent=2)+'\n')
        actor_path = Path(attempt) / 'native-actors.jsonl'
        frame_path = Path(attempt) / 'video_frames.jsonl'
        measured = analyze(actor_path, frame_path)
        if case == 'safe_operation_stop':
            measured['hazard_observation'] = analyze_hazard(actor_path, frame_path)
        measured.update(format='c179480-source-measurements-v1', case=case,
                        actor_source_sha256=hashlib.sha256(actor_path.read_bytes()).hexdigest(),
                        frame_map_sha256=hashlib.sha256(frame_path.read_bytes()).hexdigest(),
                        map_readback_sha256=hashlib.sha256(
                            (Path(attempt)/'native-map-readback.json').read_bytes()).hexdigest(),
                        physical_completion_claimed=False)
        (Path(attempt)/'source-measurements.json').write_text(
            json.dumps(measured, indent=2)+'\n')
        return receipt | {'map_readback': 'native-map-readback.json',
                          'measurements': 'source-measurements.json'}
    finally:
        for actor in reversed(actors):
            actor.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--survey', required=True)
    parser.add_argument('--case', choices=tuple(CASES), required=True)
    parser.add_argument('--candidate', choices=tuple(TUNINGS), default='primary')
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    if not Path(args.attempt).resolve().is_relative_to((repo / '.runtime-work').resolve()):
        parser.error('Generated Native attempt belongs under ignored .runtime-work')
    import carla
    survey_path = Path(args.survey)
    survey = json.loads(survey_path.read_text())
    client = carla.Client(args.host, args.port)
    client.set_timeout(20.0)
    result = run(client, carla, survey, args.attempt, args.case,
                 candidate=args.candidate)
    result['survey_sha256'] = hashlib.sha256(survey_path.read_bytes()).hexdigest()
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
