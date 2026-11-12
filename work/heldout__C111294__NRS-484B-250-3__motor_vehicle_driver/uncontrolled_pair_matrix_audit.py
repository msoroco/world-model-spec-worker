"""Independent original-source join for the seven uncontrolled highway cases."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from highway_continuity_comparison_audit import require_retained_pair_bindings


SUFFIXES = (
    'same_arrival_ending_yields', 'same_arrival_ending_enters_first',
    'separated_arrival', 'yield_release_delay-0000',
    'yield_release_delay-0001', 'yield_release_delay-0002',
    'continuing_highway',
)
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def audit(attempts):
    if len(attempts) != len(SUFFIXES):
        raise ValueError('Seven exact uncontrolled highway attempts required')
    pair_hash = topology_hash = road_hash = None
    sources = []
    for suffix, path in zip(SUFFIXES, attempts):
        root = Path(path)
        config = json.loads((root / 'config.json').read_text())
        if not config.get('selected_case_id', '').endswith('__' + suffix):
            raise ValueError('Uncontrolled pair audit case order differs')
        continuing = suffix == 'continuing_highway'
        topology_name = ('highway_pair_topology.json' if continuing
                         else 'intersection_topology.json')
        required = ('controlled_route_pair.json', 'road.xodr', topology_name,
                    'control_inventory.json', *[name + '.mkv' for name in CAMERAS])
        if any(not (root / name).is_file() for name in required):
            raise ValueError('Missing original uncontrolled route-pair source')
        binding = json.loads((root / 'controlled_route_pair.json').read_text())
        current_pair_hash = require_retained_pair_bindings(binding, binding)
        current_road_hash = digest(root / 'road.xodr')
        if binding['opendrive_sha256'] != current_road_hash:
            raise ValueError('Controlled pair OpenDRIVE differs from original road')
        inventory = json.loads((root / 'control_inventory.json').read_text())
        if (inventory.get('format') != 'worker-ending-road-original-control-inventory'
                or any(inventory.get(key) for key in
                       ('ending_landmarks', 'through_landmarks', 'junction_lights'))):
            raise ValueError('Uncontrolled pair has governing original control')
        topology = json.loads((root / topology_name).read_text())
        if str(topology['junction_id']) != binding['junction_id']:
            raise ValueError('Controlled pair junction differs from original topology')
        if continuing:
            if (topology['map_name'] != binding['map_name'] or
                    any(topology['routes'][name][:len(route)] != route
                        for name, route in binding['routes'].items())):
                raise ValueError('Continuing route differs from controlled pair')
        else:
            subject = topology['lanes'][topology['subject_approach_lane']]
            other = topology['lanes'][topology['other_approach_lane']]
            if (subject['highway_id'] != 'native-road:' + str(
                    binding['routes']['ending'][0]['road_id']) or
                    other['highway_id'] != 'native-road:' + str(
                    binding['routes']['other'][0]['road_id'])):
                raise ValueError('Ending original approach differs from controlled pair')
            current_topology_hash = digest(root / topology_name)
            if topology_hash is None:
                topology_hash = current_topology_hash
            elif topology_hash != current_topology_hash:
                raise ValueError('Uncontrolled comparison changed fixed lane topology')
        if pair_hash is None:
            pair_hash, road_hash = current_pair_hash, current_road_hash
        elif pair_hash != current_pair_hash or road_hash != current_road_hash:
            raise ValueError('Uncontrolled comparison changed selected Native pair')
        sources.append({'case_id': config['selected_case_id'],
                        'binding_sha256': digest(root / 'controlled_route_pair.json'),
                        'topology_sha256': digest(root / topology_name),
                        'road_sha256': current_road_hash})
    return {'format': 'worker-uncontrolled-pair-matrix-audit',
            'case_ids': [row['case_id'] for row in sources],
            'controlled_route_pair_sha256': pair_hash,
            'fixed_ending_topology_sha256': topology_hash,
            'source_hashes': sources, 'physical_acceptance_claimed': False,
            'legal_highway_classification_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', action='append', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.attempt)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_count': len(result['case_ids']),
                      'controlled_route_pair_sha256':
                      result['controlled_route_pair_sha256']}))


if __name__ == '__main__':
    main()
