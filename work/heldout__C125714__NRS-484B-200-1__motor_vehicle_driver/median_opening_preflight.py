"""Native-only map check for an authored C125714 median-opening reference.

This emits a route-selection receipt, not a capture or physical opening proof.
"""

import argparse
import hashlib
import json
from pathlib import Path

from median_opening_route import _validate_reference, select_median_opening_route


def check(reference, case_id):
    if case_id not in {
        'heldout__C125714__NRS-484B-200-1__motor_vehicle_driver__baseline_right_east',
        'heldout__C125714__NRS-484B-200-1__motor_vehicle_driver__baseline_right_west',
        'heldout__C125714__NRS-484B-200-1__motor_vehicle_driver__unexcepted_left',
    }:
        raise ValueError('Median-opening preflight case identity differs')
    _validate_reference(reference)
    direction = 'west' if case_id.endswith('baseline_right_west') else 'east'
    if reference.get('travel_direction') != direction:
        raise ValueError('Median-opening reference direction differs from case')
    return direction


def run(reference_path, case_id, output, host='127.0.0.1', port=2000):
    import carla  # Loaded only for a manual Native preflight.

    path = Path(reference_path)
    raw = path.read_bytes()
    reference = json.loads(raw)
    direction = check(reference, case_id)
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world_map = client.get_world().get_map()
    route, samples = select_median_opening_route(
        world_map, reference, direction=direction)
    receipt = {
        'format': 'worker-median-opening-route-preflight',
        'case_id': case_id,
        'reference_sha256': hashlib.sha256(raw).hexdigest(),
        'map_name': world_map.name,
        'road_id': route[0].road_id,
        'lane_id': route[0].lane_id,
        'opening_sample_indices': samples,
        'route_xy': [[float(w.transform.location.x),
                      float(w.transform.location.y)] for w in route],
        'physical_median_verified': False,
        'delivery_ready': False,
    }
    Path(output).write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    reference = json.loads(Path(args.reference).read_text())
    check(reference, args.case)
    if args.output:
        run(args.reference, args.case, args.output, args.host, args.port)


if __name__ == '__main__':
    main()
