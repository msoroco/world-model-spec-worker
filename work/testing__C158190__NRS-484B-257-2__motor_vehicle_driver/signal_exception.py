"""Distinct stop-sign intersection with an ego-governing dynamic signal.

CPU checks validate the authored control chain. Native readback and source
footage are still required before treating the exception as observed.
"""

import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET


STOP_SITE = Path(__file__).resolve().parent / 'native-map-plan/stop-sign-crossing.xodr'
HEAD_ID = '1581903'
CONTROLLER_ID = '1581904'


def authored_signal_map(stop_site=STOP_SITE):
    """Preserve the signed entrance and add a lane-valid controlled head."""
    document = ET.parse(stop_site).getroot()
    approach = document.find("./road[@id='158190']")
    junction = document.find("./junction[@id='158191']")
    if approach is None or junction is None:
        raise ValueError('Signed approach or junction missing')
    signals = approach.find('signals')
    stops = [] if signals is None else signals.findall('signal')
    if len(stops) != 1 or stops[0].get('type') != '206':
        raise ValueError('Exact stop sign missing from exception site')
    head = ET.SubElement(signals, 'signal', {
        'id': HEAD_ID, 'name': 'ego governing signal exception',
        's': '65', 't': '-3.8', 'zOffset': '3.0', 'hOffset': '0',
        'roll': '0', 'pitch': '0', 'orientation': '+', 'dynamic': 'yes',
        'country': 'OpenDRIVE', 'type': '1000001', 'subtype': '-1', 'value': '-1'})
    ET.SubElement(head, 'validity', {'fromLane': '-1', 'toLane': '-1'})
    controller = ET.Element('controller', {'name': 'ego signal exception controller',
                                          'id': CONTROLLER_ID})
    ET.SubElement(controller, 'control', {'signalId': HEAD_ID, 'type': '0'})
    document.insert(list(document).index(junction), controller)
    ET.SubElement(junction, 'controller', {'id': CONTROLLER_ID,
                                          'type': '0', 'sequence': '0'})
    payload = ET.tostring(document, encoding='unicode')
    validate_signal_map(payload)
    return payload


def validate_signal_map(payload):
    root = ET.fromstring(payload)
    approach = root.find("./road[@id='158190']")
    if approach is None:
        raise ValueError('Signal approach missing')
    signals = approach.findall('./signals/signal')
    if len(signals) != 2 or {s.get('type') for s in signals} != {'206', '1000001'}:
        raise ValueError('Stop sign and distinct dynamic head required')
    stop = next(s for s in signals if s.get('type') == '206')
    head = next(s for s in signals if s.get('type') == '1000001')
    if (stop.get('id') != '1581902' or stop.get('dynamic') != 'no'
            or head.get('id') != HEAD_ID or head.get('dynamic') != 'yes'
            or float(stop.get('s', -1)) >= float(head.get('s', -1))
            or float(head.get('s', -1)) >= float(approach.get('length', 0))
            or any((s.find('validity') is None or
                    (s.find('validity').get('fromLane'),
                     s.find('validity').get('toLane')) != ('-1', '-1'))
                   for s in signals)):
        raise ValueError('Signed approach control placement differs')
    controller = root.find(f"./controller[@id='{CONTROLLER_ID}']")
    junction = root.find("./junction[@id='158191']")
    refs = [] if junction is None else junction.findall('controller')
    if (controller is None or len(controller.findall('control')) != 1
            or controller.find('control').get('signalId') != HEAD_ID
            or len(refs) != 1 or refs[0].get('id') != CONTROLLER_ID):
        raise ValueError('Dynamic head lacks junction controller binding')
    return {'format': 'worker-c158190-signal-exception-site',
            'map_sha256': hashlib.sha256(payload.encode()).hexdigest(),
            'stop_signal_id': stop.get('id'), 'head_signal_id': HEAD_ID,
            'controller_id': CONTROLLER_ID, 'approach_road_id': 158190,
            'approach_lane_id': -1, 'native_governance_confirmed': False}


def readback_governing_light(world):
    """Require one Native light whose affected lane is the selected ego lane."""
    lights = [actor for actor in world.get_actors().filter('traffic.traffic_light*')
              if any(wp.road_id == 158190 and wp.lane_id == -1
                     for wp in actor.get_affected_lane_waypoints())]
    if len(lights) != 1:
        raise ValueError('Expected one Native light governing the ego approach')
    light = lights[0]
    if not hasattr(light, 'trigger_volume') or len(
            light.trigger_volume.get_world_vertices(light.get_transform())) < 4:
        raise ValueError('Native governing light lacks trigger geometry')
    return {'native_signal_id': light.id,
            'native_signal_state': str(light.get_state()),
            'source': 'Native affected-lane, trigger and state readback',
            'legal_governance_confirmed': False}


def self_check():
    """CPU-only mutation and fake Native readback checks for this variant."""
    from types import SimpleNamespace

    payload = authored_signal_map()
    receipt = validate_signal_map(payload)
    assert receipt['stop_signal_id'] == '1581902'
    assert receipt['head_signal_id'] == HEAD_ID
    try:
        validate_signal_map(payload.replace('signalId="1581903"',
                                            'signalId="missing"'))
    except ValueError as exc:
        assert 'controller binding' in str(exc)
    else:
        raise AssertionError('Wrong controller binding accepted')

    class Trigger:
        def get_world_vertices(self, transform):
            return [SimpleNamespace(x=0, y=0, z=0)] * 4 if transform == 'pose' else []

    class Actors(list):
        def filter(self, pattern):
            return self

    light = SimpleNamespace(id=31, type_id='traffic.traffic_light',
                            trigger_volume=Trigger(), get_transform=lambda: 'pose',
                            get_state=lambda: 'Green',
                            get_affected_lane_waypoints=lambda: [
                                SimpleNamespace(road_id=158190, lane_id=-1)])
    row = readback_governing_light(
        SimpleNamespace(get_actors=lambda: Actors([light])))
    assert row['native_signal_id'] == 31 and row['native_signal_state'] == 'Green'
    try:
        readback_governing_light(SimpleNamespace(get_actors=lambda: Actors([])))
    except ValueError as exc:
        assert 'one Native light' in str(exc)
    else:
        raise AssertionError('Missing governing light accepted')
    return receipt


if __name__ == '__main__':
    print(self_check())
