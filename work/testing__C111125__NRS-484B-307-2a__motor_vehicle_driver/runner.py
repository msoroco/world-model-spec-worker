"""Exact straight green case entrypoint; original site sources are required for capture."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from native_scene import inside, source, verify_site
from saved_attempt import ASSIGNMENT, CASES


def load_case(path=None):
    case = json.loads(Path(path or Path(__file__).with_name('scene.json')).read_text())
    suffix = case.get('case_suffix')
    if (case.get('assignment_id') != ASSIGNMENT or suffix not in CASES or
            case.get('case_id') != ASSIGNMENT + '__' + suffix or
            case.get('cell_id') != 'C111125' or
            case.get('law_id') != 'NRS-484B-307-2a' or
            case.get('actor') != 'motor_vehicle_driver'):
        raise ValueError('wrong exact straight-green assignment or case')
    route = case.get('route_xy')
    zone = case.get('intersection_polygon_xy')
    crosswalk = case.get('adjacent_crosswalk_polygon_xy')
    if not isinstance(route, list) or len(route) < 3 or not any(
            inside(point, zone) for point in route[1:-1]):
        raise ValueError('straight route misses intersection')
    if any(abs(float(point[1]) - float(route[0][1])) > case['straight_tolerance_m']
           for point in route):
        raise ValueError('route turns outside straight cell')
    kind, region = CASES[suffix]
    if case.get('other_user_kind') != kind or case.get('other_user_region_at_exhibition') != region:
        raise ValueError('other user differs from exact case')
    if kind is not None:
        position = case.get('other_user_spawn_xy')
        if not isinstance(position, list) or len(position) != 2:
            raise ValueError('other user spawn geometry missing')
        in_zone = inside(position, zone)
        in_crosswalk = inside(position, crosswalk)
        actual = 'intersection' if in_zone else 'adjacent_crosswalk' if in_crosswalk else 'outside'
        if actual != region:
            raise ValueError('other user spawn does not construct exhibition region')
    if suffix == 'green_pedestrian_late':
        destination = case.get('other_user_destination_xy')
        if not isinstance(destination, list) or not inside(destination, crosswalk):
            raise ValueError('late pedestrian path does not enter adjacent crosswalk')
    if (case.get('official_signal_aspects') != ['circular_green'] or
            case.get('duration_frames') != 900 or case.get('rate_hz') != 20):
        raise ValueError('sole circular green and full duration required')
    return case


def check():
    case = load_case()
    print(json.dumps({'case_id': case['case_id'], 'offline_geometry_checked': True,
                      'original_site_required_at_capture': True}))


def run_native(output, host, port):
    """Require a separately supplied original site bundle before any Native action.

    The location is set by the local operator after reviewing the Native map and
    signal head. Missing or stale sources stop before simulation. The full
    acquisition bridge owns original frames and media after that preflight.
    """
    import carla
    from native_session import capture_with_media
    from native_scene import construct_native
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore
    case = load_case()
    bundle_value = os.environ.get('C111125_ORIGINAL_SITE_BUNDLE')
    if not bundle_value:
        raise ValueError('reviewed original site bundle required')
    bundle = Path(bundle_value).resolve()
    if not bundle.is_dir() or not (bundle / 'site.json').is_file():
        raise ValueError('reviewed original site bundle missing')
    site = json.loads((bundle / 'site.json').read_text())
    verify_site(site, bundle)
    if (site['cell_id'], site['actor']) != (case['cell_id'], case['actor']):
        raise ValueError('original site differs from exact case')
    client = carla.Client(host, int(port))
    client.set_timeout(30)
    saved = snapshot(client)
    world = client.get_world()
    actors = []
    try:
        if world.get_map().name != site['native_map_name']:
            raise ValueError('Native map differs from original site')
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        blueprints = world.get_blueprint_library()
        ego_bp = blueprints.find('vehicle.tesla.model3')
        other_bp = (blueprints.find('walker.pedestrian.0001') if case['other_user_kind'] == 'pedestrian'
                    else blueprints.find('vehicle.audi.tt') if case['other_user_kind'] else None)
        spawned = construct_native(site, bundle, world, carla, ego_bp, other_bp,
                                   case['other_user_kind'])
        actors = spawned['actors']
        # Native event and camera acquisition requires the operator's reviewed
        # per-frame signal reader and surveyed context. Fail closed if absent.
        raise ValueError('original per-frame signal reader and camera rig binding required')
    finally:
        for actor in reversed(actors):
            actor.destroy()
        restore(client, saved)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        check()
    else:
        if not args.output_dir:
            parser.error('--output-dir required')
        run_native(Path(args.output_dir), args.host, args.port)


if __name__ == '__main__':
    main()
