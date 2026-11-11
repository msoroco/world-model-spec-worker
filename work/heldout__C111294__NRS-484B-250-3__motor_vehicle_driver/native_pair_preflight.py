"""Prospective CARLA-lazy route-pair preflight for two continuity captures.

Run in the local Native environment before either category capture. The pinned
worker does not run this script; it only tests the selector with fake waypoints.
"""

import argparse
import hashlib
import json
from pathlib import Path

from categorical_highway_points import select_controlled_pair
from controlled_pair_binding import bind_pair, require_expected_binding
from ending_road_control_inventory import ungoverned_route_pair


def select_and_bind(world_map, lights, *, max_spawns=300, expected=None):
    if type(max_spawns) is not int or max_spawns <= 0:
        raise ValueError('Native route search bound must be positive')
    pair = select_controlled_pair(
        world_map, max_spawns=max_spawns,
        route_accept=lambda subject, other: ungoverned_route_pair(subject, other, lights))
    pair = dict(pair)
    pair['opendrive_sha256'] = hashlib.sha256(world_map.to_opendrive().encode()).hexdigest()
    return require_expected_binding(pair, expected) if expected is not None else bind_pair(pair)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--expected')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--max-spawns', type=int, default=300)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError('Retain prior Native route-pair binding')
    expected = json.loads(Path(args.expected).read_text()) if args.expected else None
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30.)
    world = client.get_world()
    lights = list(world.get_actors().filter('traffic.traffic_light*'))
    binding = select_and_bind(world.get_map(), lights,
                              max_spawns=args.max_spawns, expected=expected)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(binding, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
