"""CARLA-lazy two-pass source capture for the C178759 witness.

Physical requests, mapped road geometry, actor motion and four RGB originals are
retained separately. No off-pavement, speeding, hazard or legal verdict is made.
"""

import argparse
import json
from math import hypot
from pathlib import Path

from following_cameras import CAMERAS, FollowingCameraCapture, LosslessSourceSink
from following_construction import apply_feedback, route_from_waypoints, spawn_pair
from following_observations import sample, write_samples
from paved_boundary import mapped_right_edges, signed_clearance
from two_pass_construction import phase_at, transition_guard, validate_schedule


CASE_ID = 'heldout__C178759__NRS-484B-650-1__motor_vehicle_driver__repeated_right_pass'


def check_config(config):
    if (config.get('selected_case_id') != CASE_ID or
            config.get('case', {}).get('case_id') != CASE_ID or
            (config.get('law_id'), config.get('cell_id'), config.get('actor')) !=
            ('NRS-484B-650-1', 'C178759', 'motor_vehicle_driver')):
        raise ValueError('Wrong C178759 exact case identity')
    if (config.get('rate_hz'), config.get('frames'), config.get('duration_s')) != (20, 2000, 100):
        raise ValueError('Two-pass capture must be 2000 frames at 20 Hz')
    if config.get('required_atoms') != [] or config.get('source_packets') != []:
        raise ValueError('Unimplemented atom or packet request')
    cameras = config.get('cameras', [])
    if [item.get('name') for item in cameras] != list(CAMERAS):
        raise ValueError('Four named source cameras required')
    for item in cameras:
        if (item.get('width'), item.get('height'), item.get('fov_deg')) != (
                *CAMERAS[item['name']][2], CAMERAS[item['name']][3]):
            raise ValueError('Original camera profile differs')
    engineering = config.get('engineering', {})
    if set(engineering) - {'route_candidate_index', 'lead_spawn_station_m',
                           'beyond_mapped_edge_m', 'reclaim_lead_speed_mps'}:
        raise ValueError('Unknown two-pass engineering knob')
    if engineering.get('route_candidate_index', 0) not in (0, 1):
        raise ValueError('Unsupported route candidate')
    if engineering.get('lead_spawn_station_m', 30) not in (25, 30, 35):
        raise ValueError('Unsupported fixed vehicle spawn station')
    if engineering.get('beyond_mapped_edge_m', 1.5) not in (1.5, 2.5):
        raise ValueError('Unsupported physical shoulder margin')
    if engineering.get('reclaim_lead_speed_mps', 20) not in (20, 22):
        raise ValueError('Unsupported lead reclaim request')
    validate_schedule()
    return CASE_ID


def _select_route(map_object, candidate_index):
    eligible = []
    for transform in map_object.get_spawn_points():
        start = map_object.get_waypoint(transform.location)
        if start is None or start.is_junction:
            continue
        try:
            route = route_from_waypoints(start, length_m=2200)
            for station in (300, 520, 720):
                waypoint = route[0][min(range(len(route[1])),
                                        key=lambda i: abs(route[1][i]-station))]
                mapped_right_edges(waypoint)
            eligible.append(route)
            if len(eligible) > candidate_index:
                return eligible[candidate_index]
        except ValueError:
            continue
    raise ValueError('No 2.2 km route with right-side mapped geometry')


def _station(route, distance, vehicle):
    location = vehicle.get_location()
    index = min(range(len(route)), key=lambda i:
                hypot(location.x-route[i].transform.location.x,
                      location.y-route[i].transform.location.y))
    return distance[index], index


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
    actors, sinks = [], {}
    cameras = pipeline = frame_map = None
    frames, trace, bodies, pass_rows = [], [], [], []
    complete = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        route, distance = _select_route(world.get_map(),
                                         engineering.get('route_candidate_index', 0))
        lead_index = min(range(len(distance)), key=lambda i:
                         abs(distance[i]-engineering.get('lead_spawn_station_m', 30)))
        ego, lead = spawn_pair(world, world.get_blueprint_library(),
                               route[0].transform, route[lead_index].transform)
        actors.extend((ego, lead))
        sinks = {name: LosslessSourceSink(output, name) for name in CAMERAS}
        cameras = FollowingCameraCapture(world, carla, ego, sinks)
        pipeline = PipelineCapture(client, ego, output, CASE_ID,
                                   required_observations=config['required_atoms'])
        frame_map = FrameMap(output/'video_frames.jsonl')
        previous_phase = None
        start_time = None
        for _ in range(config['frames']):
            ego_station, ego_index = _station(route, distance, ego)
            lead_station, lead_index = _station(route, distance, lead)
            phase = phase_at(min(ego_station, 2199.999))
            edge = mapped_right_edges(route[ego_index],
                                      engineering.get('beyond_mapped_edge_m', 1.5))
            ego_location = ego.get_location()
            lead_location = lead.get_location()
            edge_clearance = signed_clearance(ego_location,
                             edge['mapped_road_edge_xy_m'], edge['right_axis_xy'])
            transition_guard(previous_phase, phase.name,
                             ego_station-lead_station, edge_clearance)
            previous_phase = phase.name
            waypoint = route[min(ego_index+3, len(route)-1)]
            if phase.ego_target == 'right_of_paved_edge':
                ego_target = mapped_right_edges(waypoint,
                    engineering.get('beyond_mapped_edge_m', 1.5))['target_xy_m']
            else:
                point = waypoint.transform.location
                ego_target = (point.x, point.y)
            lead_point = route[min(lead_index+3, len(route)-1)].transform.location
            lead_speed = (engineering.get('reclaim_lead_speed_mps', 20)
                          if phase.name == 'lead_reclaim_request'
                          else phase.lead_speed_mps)
            apply_feedback(ego, carla, ego_target, phase.ego_speed_mps)
            apply_feedback(lead, carla, (lead_point.x, lead_point.y), lead_speed)
            frame = world.tick()
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Native snapshot frame differs')
            if start_time is None:
                start_time = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds-start_time
            cameras.wait_for_frame(frame)
            pipeline.capture(frame, time_s)
            frame_map.append(frame, time_s)
            ego_location = ego.get_location()
            lead_location = lead.get_location()
            current_station, current_index = _station(route, distance, ego)
            current_lead_station, _ = _station(route, distance, lead)
            current_edge = mapped_right_edges(route[current_index],
                engineering.get('beyond_mapped_edge_m', 1.5))
            trace.append({'frame': frame, 'time_s': time_s,
                          'driver_id': 'ego-actor-'+str(ego.id),
                          'x_m': float(ego_location.x), 'y_m': float(ego_location.y)})
            pass_rows.append({'frame': frame, 'time_s': time_s,
                'ego_actor_id': int(ego.id), 'fixed_overtaken_actor_id': int(lead.id),
                'ego_station_m': current_station, 'lead_station_m': current_lead_station,
                'ego_xy_m': [float(ego_location.x), float(ego_location.y)],
                'lead_xy_m': [float(lead_location.x), float(lead_location.y)],
                'mapped_driving_edge_xy_m': list(current_edge['driving_edge_xy_m']),
                'mapped_road_edge_xy_m': list(current_edge['mapped_road_edge_xy_m']),
                'right_axis_xy': list(current_edge['right_axis_xy']),
                'right_of_mapped_road_edge_m': signed_clearance(ego_location,
                    current_edge['mapped_road_edge_xy_m'], current_edge['right_axis_xy']),
                'road_id': current_edge['road_id'],
                'driving_lane_id': current_edge['driving_lane_id'],
                'shoulder_lane_id': current_edge['shoulder_lane_id'],
                'requested_phase': phase.name,
                'pavement_surface_legal_judgment': None,
                'right_pass_legal_judgment': None})
            bodies.append(sample(frame, time_s, ego, lead,
                                 requested_phase=phase.name,
                                 map_speed_limit_kmh=float(ego.get_speed_limit())))
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
        world.apply_settings(original_settings)
        restored = (world.get_settings().synchronous_mode == original_settings.synchronous_mode
                    and world.get_settings().fixed_delta_seconds == original_settings.fixed_delta_seconds)
        if not restored:
            raise ValueError('Native world settings restoration differs')
    if not complete or len(frames) != config['frames']:
        raise ValueError('Native two-pass capture incomplete')
    write_samples(output/'following_sources.jsonl', bodies)
    (output/'driving_trace.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in trace))
    (output/'right_pass_sources.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in pass_rows))
    (output/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind':'native', 'diagnostic_fixture':False,
        'original_frames':len(frames), 'fixed_overtaken_actor_id':int(lead.id),
        'pavement_and_legal_review_pending':True})+'\n')
    seal_capture(output, frames=len(frames), restoration={'restored':True},
                 errors=[], encoder_exit_codes={name:0 for name in CAMERAS},
                 context={'native_map_name':world.get_map().name,
                          'fixed_overtaken_actor_id':int(lead.id),
                          'pavement_surface_review_required':True})


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
