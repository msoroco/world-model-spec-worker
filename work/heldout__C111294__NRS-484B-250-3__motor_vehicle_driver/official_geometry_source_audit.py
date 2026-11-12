"""Join a retained governed Native route binding to original saved sources."""

import argparse
import json
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree

from official_geometry_binding import _digest


def _read(root, name):
    path = root / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing official original source: ' + name)
    return json.loads(path.read_text()) if name.endswith('.json') else path.read_bytes()


def _topology_path(topology, role):
    lanes = topology['lanes']
    current = topology[f'{role}_approach_lane']
    rows = []
    seen = set()
    while True:
        if current in seen or current not in lanes:
            raise ValueError('Official original topology path is cyclic or missing')
        seen.add(current)
        node = lanes[current]
        rows.append((int(node['road_id']), int(node['lane_id']),
                     None if node['junction_id'] is None else str(node['junction_id'])))
        successors = node.get('successors', [])
        if not successors:
            return rows
        if len(successors) != 1:
            raise ValueError('Official original topology path is ambiguous')
        current = successors[0]


def _check_opendrive(opendrive, binding):
    """Verify that the bound lane IDs, junction and signal exist in the map bytes."""
    try:
        root = ElementTree.fromstring(opendrive)
    except ElementTree.ParseError as exc:
        raise ValueError('Official OpenDRIVE source is malformed') from exc
    if root.tag != 'OpenDRIVE':
        raise ValueError('Official OpenDRIVE root differs')
    roads = {int(road.attrib['id']): road for road in root.findall('road')}
    junction = str(binding['junction_id'])
    if junction not in {item.get('id') for item in root.findall('junction')}:
        raise ValueError('Official OpenDRIVE junction is missing')
    for role in ('subject', 'other'):
        for point in binding['routes'][role]:
            road = roads.get(int(point['road_id']))
            if road is None:
                raise ValueError('Official OpenDRIVE route road is missing: ' + role)
            expected_junction = point['junction_id']
            if expected_junction is not None and road.get('junction') != junction:
                raise ValueError('Official OpenDRIVE route junction differs: ' + role)
            lane_id = str(point['lane_id'])
            if not any(lane.get('id') == lane_id for lane in road.findall('.//laneSection//lane')):
                raise ValueError('Official OpenDRIVE route lane is missing: ' + role)
    governing = binding['governing_device']
    road = roads.get(int(governing['affected_road_id']))
    if road is None:
        raise ValueError('Official OpenDRIVE governing road is missing')
    signal_id = governing['opendrive_signal_id']
    lane_id = int(governing['affected_lane_id'])
    signals = [item for item in road.findall('.//signals/signal') +
               road.findall('.//signals/signalReference')
               if item.get('id') == signal_id]
    if not signals:
        raise ValueError('Official OpenDRIVE governing signal is missing')
    if not any(any(int(valid.get('fromLane')) <= lane_id <= int(valid.get('toLane'))
                   for valid in signal.findall('validity')) for signal in signals):
        raise ValueError('Official OpenDRIVE governing signal lane differs')


def audit(root):
    root = Path(root)
    binding = _read(root, 'official_geometry_binding.json')
    topology = _read(root, 'intersection_topology.json')
    device = _read(root, 'official_device_context.json')
    opendrive = _read(root, 'road.xodr')
    if binding.get('format') != 'worker-official-native-geometry' or binding.get('geometry_sha256') != _digest(binding):
        raise ValueError('Official Native geometry binding is stale')
    if sha256(opendrive).hexdigest() != binding.get('opendrive_sha256'):
        raise ValueError('Official OpenDRIVE original source differs from binding')
    _check_opendrive(opendrive, binding)
    junction = str(binding['junction_id'])
    if str(topology.get('junction_id')) != junction or str(device.get('junction_id')) != junction:
        raise ValueError('Official original junction differs from binding')
    for role, key in (('subject', 'subject'), ('other', 'other')):
        expected = [(int(row['road_id']), int(row['lane_id']), row['junction_id'])
                    for row in binding['routes'][key]]
        observed = _topology_path(topology, role)
        # Capture extends selected exit routes beyond the junction to give the
        # controller a target. The bound selection must be an exact prefix.
        if len(observed) < len(expected) or observed[:len(expected)] != expected:
            raise ValueError('Official original route differs from binding: ' + role)
    governing = binding['governing_device']
    if (device.get('opendrive_signal_id') != governing['opendrive_signal_id'] or
            int(device.get('affected_road_id')) != governing['affected_road_id'] or
            int(device.get('affected_lane_id')) != governing['affected_lane_id']):
        raise ValueError('Official original affected-lane signal differs from binding')
    return {'format': 'worker-official-original-geometry-audit',
            'geometry_sha256': binding['geometry_sha256'],
            'opendrive_sha256': binding['opendrive_sha256'],
            'junction_id': junction, 'signal_id': governing['opendrive_signal_id'],
            'legal_official_status_claimed': False,
            'physical_realization_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError('Retain prior official geometry source audit')
    output.write_text(json.dumps(audit(args.attempt), indent=2) + '\n')
