"""Build source-consistent synthetic T-junction originals for CPU diagnostics.

These bytes exercise source joins. They do not identify a CARLA map or establish
that an official device physically governs a real approach.
"""

import copy
import hashlib

from official_geometry_binding import _digest


ROUTES = {
    'subject': [(1, -1, None, [-8.0, 0.0]),
                (5, -1, '42', [0.0, 0.0]),
                (2, -1, None, [8.0, 0.0])],
    'other': [(3, -1, None, [0.0, -8.0]),
              (6, -1, '42', [0.0, 0.0]),
              (3, -1, None, [0.0, 8.0])],
}


def _road(road_id, junction, x, y, heading, signal=False):
    device = ('<signals><signal id="signal-8" s="2" t="0" name="synthetic" '
              'dynamic="yes" orientation="+" zOffset="0" country="US" type="1000001" '
              'subtype="-1" value="0" height="1" width="1"><validity fromLane="-1" '
              'toLane="-1"/></signal></signals>') if signal else '<signals/>'
    return (f'<road name="diagnostic-{road_id}" length="16" id="{road_id}" '
            f'junction="{junction}"><link/><planView><geometry s="0" x="{x}" '
            f'y="{y}" hdg="{heading}" length="16"><line/></geometry></planView>'
            '<elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/>'
            '</elevationProfile><lateralProfile/><lanes><laneSection s="0">'
            '<left/><center><lane id="0" type="none" level="false"/></center>'
            '<right><lane id="-1" type="driving" level="false"><link/>'
            '<width sOffset="0" a="3.5" b="0" c="0" d="0"/>'
            '</lane></right></laneSection></lanes>' + device + '</road>')


def synthetic_opendrive():
    roads = [_road(1, '-1', -16, 0, 0, True),
             _road(2, '-1', 0, 0, 0),
             _road(3, '-1', 0, -16, 1.57079632679),
             _road(5, '42', -2, 0, 0),
             _road(6, '42', 0, -2, 1.57079632679)]
    return ('<OpenDRIVE><header revMajor="1" revMinor="4" name="diagnostic-T" '
            'version="1" north="16" south="-16" east="16" west="-16"/>'
            + ''.join(roads) + '<junction name="diagnostic" id="42"/></OpenDRIVE>')


def rebuild(diagnostic):
    """Return a copied diagnostic whose original map/topology/device join."""
    result = copy.deepcopy(diagnostic)
    files = result['files']
    xodr = synthetic_opendrive()
    topology = copy.deepcopy(files['intersection_topology.json'])
    if isinstance(topology, str):
        import json
        topology = json.loads(topology)
    for role, prefix in (('subject', 's'), ('other', 'o')):
        for index, (road, lane, junction, _) in enumerate(ROUTES[role]):
            node = topology['lanes'][f'{prefix}{index}']
            node['road_id'] = road
            node['lane_id'] = lane
            node['junction_id'] = junction
            node['highway_id'] = f'native-road:{road}' if junction is None else 'junction'
    device = copy.deepcopy(files['official_device_context.json'])
    if isinstance(device, str):
        import json
        device = json.loads(device)
    device.update({'opendrive_signal_id': 'signal-8', 'affected_road_id': 1,
                   'affected_lane_id': -1, 'junction_id': '42'})
    binding = {'format': 'worker-official-native-geometry',
               'map_name': 'diagnostic-T', 'junction_id': '42',
               'opendrive_sha256': hashlib.sha256(xodr.encode()).hexdigest(),
               'routes': {role: [
                   {'road_id': road, 'lane_id': lane, 'junction_id': junction, 'xy': xy}
                   for road, lane, junction, xy in path]
                   for role, path in ROUTES.items()},
               'governing_device': {'opendrive_signal_id': 'signal-8',
                                    'affected_road_id': 1, 'affected_lane_id': -1},
               'legal_official_status_claimed': False}
    binding['geometry_sha256'] = _digest(binding)
    import json
    files['road.xodr'] = xodr
    files['intersection_topology.json'] = json.dumps(topology, indent=2) + '\n'
    files['official_device_context.json'] = json.dumps(device, indent=2) + '\n'
    files['official_geometry_binding.json'] = json.dumps(binding, indent=2) + '\n'
    return result
