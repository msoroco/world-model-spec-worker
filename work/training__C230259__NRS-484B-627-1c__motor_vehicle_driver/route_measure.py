"""Source-bound saved measurement of an original route attempt.

The graph is an authored opportunity and the track is an observation. Neither
alone settles statutory possibility or impediment.
"""
import hashlib
import json
import math
import xml.etree.ElementTree as ET

FRAMES = 900
RATE = 20
CAMERAS = {'overview', 'approach', 'reference_corner', 'driver_reference'}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def measure(trace_bytes, context_bytes, road_bytes, frame_map_bytes):
    context = json.loads(context_bytes)
    require(context.get('source_kind') in ('native_saved_sample', 'synthetic_fixture'),
            'route source kind missing')
    require(context.get('road_xodr_sha256') == sha(road_bytes),
            'original road source hash differs')
    root = ET.fromstring(road_bytes)
    roads = {int(road.get('id')) for road in root.findall('road')}
    links = {(int(c.get('incomingRoad')), int(c.get('connectingRoad')))
             for c in root.findall('junction/connection')}
    require({1, 2, 4} <= roads and (1, 2) in links,
            'main route topology missing')
    authored_alternate = 3 in roads and (1, 3) in links
    graph = context.get('route_graph', {})
    require(graph.get('start_road_id') == 1 and graph.get('main_road_id') == 2
            and graph.get('destination_road_id') == 4
            and graph.get('alternate_road_id') == (3 if authored_alternate else None),
            'route context differs from original road')
    rows = [json.loads(line) for line in trace_bytes.splitlines() if line]
    mappings = [json.loads(line) for line in frame_map_bytes.splitlines() if line]
    require(len(rows) == len(mappings) == FRAMES,
            'full original route and camera window missing')
    seen_road_ids, follower_gaps = [], []
    prior_native_frame = -1
    first_ego_id = None
    first_following_ids = None
    for index, (row, frame) in enumerate(zip(rows, mappings)):
        native_frame = row.get('native_frame')
        require(type(native_frame) is int and native_frame > prior_native_frame
                and frame.get('native_frame') == native_frame
                and frame.get('video_frame') == row.get('video_frame') == index,
                'original route/frame join differs')
        prior_native_frame = native_frame
        require(abs(row.get('time_s', -999) - frame.get('time_s', 999)) <= .005
                and abs(row['time_s'] - index / RATE) <= .06,
                'original route/camera time join differs')
        require(set(row.get('camera_native_frames', {})) == CAMERAS
                and all(value == native_frame for value in row['camera_native_frames'].values()),
                'original four-camera frame join differs')
        ego = row.get('ego', {})
        require(ego.get('road_id') in roads and ego.get('lane_id') == -1,
                'subject original road/lane source missing')
        require(isinstance(ego.get('speed_mps'), (int, float))
                and math.isfinite(ego['speed_mps']), 'subject velocity source missing')
        require(isinstance(ego.get('xy_m'), list) and len(ego['xy_m']) == 2,
                'subject position source missing')
        first_ego_id = first_ego_id or ego.get('actor_id')
        require(first_ego_id and ego.get('actor_id') == first_ego_id,
                'subject identity changed')
        followers = row.get('following')
        require(isinstance(followers, list) and len(followers) == 2,
                'two original following vehicles missing')
        following_ids = [f.get('actor_id') for f in followers]
        if first_following_ids is None:
            first_following_ids = following_ids
        require(all(following_ids) and following_ids == first_following_ids
                and len(set(following_ids + [first_ego_id])) == 3,
                'following actor identities changed')
        for follower in followers:
            require(follower.get('road_id') in roads and follower.get('lane_id') == -1,
                    'following original road/lane source missing')
            require(isinstance(follower.get('xy_m'), list)
                    and len(follower['xy_m']) == 2
                    and isinstance(follower.get('speed_mps'), (int, float))
                    and math.isfinite(follower['speed_mps']),
                    'following position or velocity source missing')
        if all(follower['road_id'] == 1 for follower in followers) and ego['road_id'] == 1:
            gaps = [ego['xy_m'][0] - f['xy_m'][0] for f in followers]
            if all(gap > 0 for gap in gaps):
                follower_gaps.append(gaps)
        seen_road_ids.append(ego['road_id'])
    require(len(follower_gaps) >= 20, 'immediately following approach source missing')
    require(1 in seen_road_ids, 'original approach missing')
    observed_alternate = 3 in seen_road_ids
    require(not observed_alternate or authored_alternate,
            'observed alternate not connected in original road')
    return {'format': 'c230259-route-measurement-v1',
            'source_kind': context['source_kind'],
            'source_sha256': {'route-trace.jsonl': sha(trace_bytes),
                              'route-context.json': sha(context_bytes),
                              'road.xodr': sha(road_bytes),
                              'video_frames.jsonl': sha(frame_map_bytes)},
            'frames': FRAMES, 'duration_s': FRAMES / RATE,
            'authored_alternate_connected': authored_alternate,
            'observed_alternate_road': observed_alternate,
            'observed_alternate_road_frames': seen_road_ids.count(3),
            'observed_destination_road': 4 in seen_road_ids,
            'immediately_following_approach_frames': len(follower_gaps),
            'minimum_approach_follower_gap_m': min(g[0] for g in follower_gaps),
            'controlled_access_designation_independently_verified':
                bool(context.get('controlled_access_designation_independently_verified')),
            'alternate_route_usability_physically_verified':
                bool(context.get('alternate_route_usability_physically_verified')),
            'impediment_legally_determined': False,
            'alternate_route_legally_possible_determined': False}
