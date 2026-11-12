"""Join a retained governed Native route binding to original saved sources."""

import argparse
import json
from hashlib import sha256
from pathlib import Path

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
    junction = str(binding['junction_id'])
    if str(topology.get('junction_id')) != junction or str(device.get('junction_id')) != junction:
        raise ValueError('Official original junction differs from binding')
    for role, key in (('subject', 'subject'), ('other', 'other')):
        expected = [(int(row['road_id']), int(row['lane_id']), row['junction_id'])
                    for row in binding['routes'][key]]
        if _topology_path(topology, role) != expected:
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
