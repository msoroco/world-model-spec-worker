"""Select a governed Native T junction for two fixed-geometry signal cases."""

import argparse
import json
from pathlib import Path

from ending_road_device import select_ending_approach_device
from ending_road_route import select_t_routes
from official_geometry_binding import bind_geometry


def select_binding(world):
    world_map = world.get_map()
    lights = list(world.get_actors().filter('traffic.traffic_light*'))

    def governed(ending, through):
        try:
            select_ending_approach_device(lights, ending['path'], ending['junction_id'])
            return True
        except ValueError:
            return False

    routes = select_t_routes(world_map, route_accept=governed)
    selected = select_ending_approach_device(
        lights, routes['subject'], routes['junction_id'])
    return bind_geometry(world_map, routes, selected)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError('Retain prior official Native geometry preflight')
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30.)
    binding = select_binding(client.get_world())
    output.write_text(json.dumps(binding, indent=2) + '\n')


if __name__ == '__main__':
    main()
