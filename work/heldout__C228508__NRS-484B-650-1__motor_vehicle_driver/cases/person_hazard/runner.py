"""CARLA-lazy original following capture for the C228508 primary case."""

import argparse
import json
from math import hypot, sin, cos, pi
from pathlib import Path

from following_cameras import CAMERAS, FollowingCameraCapture, LosslessSourceSink
from following_construction import (PHASES, apply_feedback, phase_at,
                                    route_from_waypoints, spawn_pair,
                                    validate_schedule)
from following_observations import sample, write_samples
from device_lane_candidates import write_candidates
from device_lane_construction import lane_target, select_site
from person_hazard_construction import spawn_walker, control_walker, person_sample


PREFIX = 'heldout__C228508__NRS-484B-650-1__motor_vehicle_driver__'
CASES = (PREFIX + 'repeated_following', PREFIX + 'one_secondary_act',
         PREFIX + 'no_speed', PREFIX + 'person_hazard')


def check_config(config):
    if (config.get('selected_case_id') not in CASES or
            config.get('case', {}).get('case_id') != config.get('selected_case_id') or
            (config.get('law_id'), config.get('cell_id'), config.get('actor')) !=
            ('NRS-484B-650-1', 'C228508', 'motor_vehicle_driver')):
        raise ValueError('Wrong C228508 exact case identity')
    if (config.get('rate_hz'), config.get('frames'), config.get('duration_s')) != (20, 2000, 100):
        raise ValueError('Following capture must be 2000 frames at 20 Hz')
    if not isinstance(config['case'].get('recording_description'), dict):
        raise ValueError('Missing exact recording description')
    cameras = config.get('cameras', [])
    if [item.get('name') for item in cameras] != list(CAMERAS):
        raise ValueError('Four named source cameras required')
    for item in cameras:
        profile = CAMERAS[item['name']]
        if (item.get('width'), item.get('height'), item.get('fov_deg')) != (
                *profile[2], profile[3]):
            raise ValueError('Source camera profile differs')
    if config.get('required_atoms') != [] or config.get('source_packets') != []:
        raise ValueError('Unimplemented atom or packet request')
    engineering = config.get('engineering', {})
    if set(engineering) - {'route_candidate_index', 'lead_spawn_station_m',
                           'closing_lead_speed_mps', 'requested_speed_cap_mps',
                           'lane_excursion_fraction', 'person_spawn_station_m',
                           'person_crossing_speed_mps', 'person_blueprint_index'}:
        raise ValueError('Unknown following engineering knob')
    if engineering.get('route_candidate_index', 0) not in (0, 1):
        raise ValueError('Unsupported route candidate index')
    if engineering.get('lead_spawn_station_m', 30) not in (30, 40):
        raise ValueError('Unsupported lead spawn station')
    if engineering.get('closing_lead_speed_mps', 11) not in (11, 9):
        raise ValueError('Unsupported lead closing speed')
    if engineering.get('lane_excursion_fraction', .6) not in (.6, .75):
        raise ValueError('Unsupported physical lane excursion fraction')
    if engineering.get('person_spawn_station_m',200) not in (200,240):
        raise ValueError('Unsupported person spawn station')
    if engineering.get('person_crossing_speed_mps',1.6) not in (1.6,2.1):
        raise ValueError('Unsupported person crossing speed')
    if engineering.get('person_blueprint_index',0) not in (0,1):
        raise ValueError('Unsupported person blueprint index')
    if config.get('official_control_source') != 'Native traffic-light actor and OpenDRIVE ID for independent review':
        raise ValueError('Native control source review premise missing')
    speed_cap = engineering.get('requested_speed_cap_mps', 24)
    if speed_cap not in (24, 13):
        raise ValueError('Unsupported ego speed cap')
    if speed_cap != (13 if config['selected_case_id'].endswith('__no_speed') else 24):
        raise ValueError('Wrong ego speed request for exact case')
    encounters = config.get('closing_encounters')
    if encounters != (1 if config['selected_case_id'].endswith('__one_secondary_act') else 2):
        raise ValueError('Wrong secondary-act count for exact case')
    validate_schedule()
    return config['selected_case_id']


def _select_route(map_object, *, candidate_index=0):
    eligible = []
    for transform in map_object.get_spawn_points():
        start = map_object.get_waypoint(transform.location)
        if start is None or start.is_junction:
            continue
        try:
            route = route_from_waypoints(start, length_m=2200)
            eligible.append(route)
            if len(eligible) > candidate_index:
                return eligible[candidate_index]
        except ValueError:
            continue
    raise ValueError('No requested 2.2 km continuous same-lane route on supplied Native map')


def _station(route, distance, vehicle):
    location = vehicle.get_location()
    nearest = min(range(len(route)),
                  key=lambda index: hypot(location.x-route[index].transform.location.x,
                                          location.y-route[index].transform.location.y))
    return distance[nearest], nearest


def run(output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture

    output = Path(output_dir)
    config = json.loads((output/'config.json').read_text())
    check_config(config)
    engineering = config.get('engineering', {})
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    original_settings = world.get_settings()
    actors = []
    cameras = pipeline = frame_map = site = original_light_state = None
    sinks = {}
    frames, trace, bodies, signal_lane_rows, person_rows = [], [], [], [], []
    complete = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        site = select_site(world.get_map(),
                           world.get_actors().filter('traffic.traffic_light*'),
                           candidate_index=engineering.get('route_candidate_index', 0))
        route, distance = site['route'], site['distance_m']
        original_light_state = site['light'].get_state()
        person,person_direction=spawn_walker(world,carla,route,distance,
            engineering.get('person_spawn_station_m',200),
            blueprint_index=engineering.get('person_blueprint_index',0))
        actors.append(person)
        lead_index = min(range(len(distance)),
                         key=lambda index: abs(distance[index] - engineering.get('lead_spawn_station_m', 30)))
        ego, lead = spawn_pair(world, world.get_blueprint_library(),
                               route[0].transform, route[lead_index].transform)
        actors.extend((ego, lead))
        sinks = {name: LosslessSourceSink(output, name) for name in CAMERAS}
        cameras = FollowingCameraCapture(world, carla, ego, sinks)
        pipeline = PipelineCapture(client, ego, output, config['selected_case_id'],
                                   required_observations=config['required_atoms'])
        frame_map = FrameMap(output/'video_frames.jsonl')
        start_time = None
        for _ in range(config['frames']):
            ego_station, ego_index = _station(route, distance, ego)
            lead_station, lead_index = _station(route, distance, lead)
            phase = phase_at(min(ego_station, PHASES[-1].end_m - .001))
            suppressed = (config['closing_encounters'] == 1 and
                          phase.label == 'second_closing_request')
            phase_label = 'second_encounter_suppressed' if suppressed else phase.label
            ego_target_xy = lane_target(site, ego_station, ego_index,
                                        engineering.get('lane_excursion_fraction', .6))
            lead_target = route[min(lead_index + 3, len(route)-1)].transform.location
            site['light'].set_state(carla.TrafficLightState.Red)
            if site['light'].get_state() != carla.TrafficLightState.Red:
                raise ValueError('Native red-light readback differs')
            control_walker(person,carla,person_direction,
                           engineering.get('person_crossing_speed_mps',1.6)
                           if 120<=ego_station<300 else 0)
            apply_feedback(ego, carla, ego_target_xy,
                           min(phase.ego_target_mps,
                               engineering.get('requested_speed_cap_mps', 24)))
            apply_feedback(lead, carla, (lead_target.x, lead_target.y),
                           (18 if suppressed else
                            engineering.get('closing_lead_speed_mps', 11)
                            if 'closing_request' in phase.label
                            else phase.lead_target_mps))
            frame = world.tick()
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Native snapshot frame differs')
            if start_time is None:
                start_time = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds - start_time
            cameras.wait_for_frame(frame)
            pipeline.capture(frame, time_s)
            frame_map.append(frame, time_s)
            ego_location = ego.get_location()
            trace.append({'frame':frame, 'time_s':time_s,
                          'x_m':float(ego_location.x), 'y_m':float(ego_location.y)})
            person_rows.append(person_sample(frame,time_s,ego,person,ego_station))
            bodies.append(sample(frame, time_s, ego, lead,
                                 requested_phase=phase_label,
                                 map_speed_limit_kmh=float(ego.get_speed_limit())))
            waypoint = route[ego_index]
            center = waypoint.transform.location
            yaw = waypoint.transform.rotation.yaw*pi/180
            lateral_shift = abs(-sin(yaw)*(ego_location.x-center.x) +
                                 cos(yaw)*(ego_location.y-center.y))
            signal_lane_rows.append({
                'frame':frame, 'time_s':time_s, 'ego_station_m':ego_station,
                'stop_station_m':site['stop_station_m'],
                'traffic_light_actor_id':site['light_actor_id'],
                'opendrive_id':site['opendrive_id'],
                'native_light_state':str(site['light'].get_state()),
                'lateral_center_shift_m':lateral_shift,
                'marked_lane_width_m':float(waypoint.lane_width),
                'marked_lane_id':int(waypoint.lane_id),
                'adjacent_lane_id':site['adjacent_lane_id'],
                'official_control_legal_judgment':None,
                'marked_lane_legal_judgment':None})
            frames.append(frame)
        cameras.verify(frames)
        complete = True
    finally:
        if frame_map is not None:
            frame_map.close()
        if pipeline is not None:
            pipeline.close(confirmed=complete)
        if cameras is not None:
            cameras.close()
        for sink in sinks.values():
            sink.close()
        for actor in reversed(actors):
            actor.destroy()
        try:
            if site is not None and original_light_state is not None:
                site['light'].set_state(original_light_state)
                if site['light'].get_state() != original_light_state:
                    raise ValueError('Traffic-light restoration readback differs')
        finally:
            world.apply_settings(original_settings)
        restored = (world.get_settings().synchronous_mode == original_settings.synchronous_mode and
                    world.get_settings().fixed_delta_seconds == original_settings.fixed_delta_seconds)
        if not restored:
            raise ValueError('Native world settings restoration differs')
    if not complete or len(frames) != config['frames']:
        raise ValueError('Native following capture incomplete')
    following_source = write_samples(output/'following_sources.jsonl', bodies)
    (output/'driving_trace.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in trace))
    device_source = output/'device_lane_sources.jsonl'
    device_source.write_text(''.join(json.dumps(row)+'\n' for row in signal_lane_rows))
    person_source = output/'person_sources.jsonl'
    person_source.write_text(''.join(json.dumps(row)+'\n' for row in person_rows))
    # Original-source geometry yields unreviewed engineering frame candidates only.
    write_candidates(following_source, device_source, person_source, output/'event_annotations.json')
    (output/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind':'native', 'diagnostic_fixture':False,
        'original_frames':len(frames), 'unreviewed_event_annotations':True})+'\n')
    seal_capture(output, frames=len(frames), restoration={'restored':True},
                 errors=[], encoder_exit_codes={name:0 for name in CAMERAS},
                 context={'native_map_name':world.get_map().name,
                          'road_id':route[0].road_id,
                          'lane_id':route[0].lane_id,
                          'traffic_light_actor_id':site['light_actor_id'],
                          'opendrive_id':site['opendrive_id'],
                          'person_actor_id':person.id})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        check_config(json.loads(Path('config.json').read_text()))
        return
    if not args.output_dir:
        parser.error('--output-dir required for Native capture')
    run(args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
