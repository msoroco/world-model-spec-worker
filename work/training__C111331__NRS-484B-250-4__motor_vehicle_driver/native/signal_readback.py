"""Original CARLA signal acquisition for the two governed incoming lanes.

Call once after world import and on each capture tick. Missing or ambiguous
Native heads fail capture; authored OpenDRIVE XML alone is not evidence.
"""
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

INCOMING = {(250, -1), (253, -1)}


def map_check(path):
    path = Path(path)
    root = ET.parse(path).getroot()
    found = {}
    for road_id, signal_id in ((250, '701'), (253, '702')):
        road = next((x for x in root.findall('road') if x.get('id') == str(road_id)), None)
        if road is None or road.get('junction') != '-1':
            raise ValueError('Original incoming road missing')
        signal = road.find('./signals/signal')
        objects = road.findall('./objects/object')
        if (signal is None or signal.get('id') != signal_id or
                signal.get('type') != '1000001' or signal.get('dynamic') != 'yes' or
                len(objects) != 2 or objects[0].get('type') != 'roadMark' or
                objects[1].get('type') != 'crosswalk' or
                not float(objects[0].get('s')) < float(objects[1].get('s')) < float(road.get('length'))):
            raise ValueError('Original signal or stop-reference geometry differs')
        found[str(road_id)] = {'signal_id': signal_id,
                               'marked_line_s_m': float(objects[0].get('s')),
                               'crosswalk_s_m': float(objects[1].get('s'))}
    return {'map_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'incoming': found}


def readback(world, carla, frame, time_s):
    lights = [actor for actor in world.get_actors()
              if actor.type_id == 'traffic.traffic_light']
    if len(lights) < 2:
        raise ValueError('Native installed vehicular signal missing')
    observed = {}
    for light in lights:
        try:
            lanes = {(wp.road_id, wp.lane_id)
                     for wp in light.get_affected_lane_waypoints()}
            state = light.get_state()
            boxes = light.get_light_boxes()
        except Exception as exc:
            raise ValueError('Native signal readback unavailable') from exc
        governed = lanes & INCOMING
        if not governed:
            continue
        if state != carla.TrafficLightState.Off or not boxes:
            raise ValueError('Native governing head is lit or lacks light-box geometry')
        for lane in governed:
            if lane in observed:
                raise ValueError('Ambiguous Native governing signal')
            observed[lane] = {'actor_id': light.id, 'state': str(state),
                              'affected_lanes': sorted([list(x) for x in lanes]),
                              'light_box_count': len(boxes)}
    if set(observed) != INCOMING:
        raise ValueError('Each incoming lane needs an original Off signal')
    return {'frame': frame, 'time_s': time_s, 'source_kind': 'original_native',
            'governing_heads': {f'{r}:{lane}': value for (r, lane), value in observed.items()},
            'uncovered_pixels_reviewed': False, 'official_authority_inferred': False}


def configure_outage(world, carla):
    """Command both imported Native approach heads dark and frozen.

    The next tick must still be verified with readback; this command is a
    construction action, not evidence that the scene rendered dark heads.
    """
    found = set()
    for light in world.get_actors():
        if light.type_id != 'traffic.traffic_light':
            continue
        lanes = {(wp.road_id, wp.lane_id)
                 for wp in light.get_affected_lane_waypoints()}
        governed = lanes & INCOMING
        if governed:
            if governed & found:
                raise ValueError('Ambiguous Native governing signal')
            light.freeze(True)
            light.set_state(carla.TrafficLightState.Off)
            found.update(governed)
    if found != INCOMING:
        raise ValueError('Native imported signal missing for incoming lane')
    return {'commanded_incoming_lanes': sorted([list(x) for x in found]),
            'state_requested': 'Off', 'readback_required': True}
