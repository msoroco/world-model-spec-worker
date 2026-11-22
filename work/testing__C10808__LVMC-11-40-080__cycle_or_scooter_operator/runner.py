"""Draft bicycle dismount construction for the assigned prohibited U-turn cell.

Native capture/finalization is still required. CARLA is imported only on explicit
execution. The prop identifiers are checked against the local blueprint library.
"""
import argparse
import json
import math
from pathlib import Path

SCENE = Path(__file__).with_name('scene.json')


def load_scene(path=SCENE):
    scene = json.loads(Path(path).read_text())
    if scene['law_id'] != 'LVMC-11-40-080' or scene['cell_id'] != 'C10808':
        raise ValueError('wrong law or cell identity')
    if scene['actor'] != 'cycle_or_scooter_operator':
        raise ValueError('wrong operator identity')
    if not (scene['approach_x_m'] < scene['sign']['x_m'] < scene['dismount_x_m'] < scene['turn_x_m']):
        raise ValueError('sign/dismount/turn order is invalid')
    if not scene['turn_x_m'] > scene['exit_x_m']:
        raise ValueError('return path must reverse longitudinal direction')
    if scene['alley_half_width_m'] <= 0 or scene['control']['dismount_hold_s'] <= 0:
        raise ValueError('turning width and dismount interval must be positive')
    return scene


def path_points(scene):
    """The reversal begins only after the dismount station."""
    half = scene['alley_half_width_m']
    turn = [(scene['dismount_x_m'], -half / 2),
                  (scene['turn_x_m'], -half / 2),
                  (scene['turn_x_m'] + half, 0.0),
                  (scene['turn_x_m'], half / 2),
                  (scene['exit_x_m'], half / 2)]
    approach = [(scene['approach_x_m'], -half / 2), (scene['dismount_x_m'], -half / 2)]
    return {'mounted': approach if scene['dismount_enabled'] else approach + turn[1:],
            'afoot': turn if scene['dismount_enabled'] else []}


def choose_blueprint(library, pattern):
    matches = list(library.filter(pattern))
    if not matches:
        raise ValueError('required physical blueprint unavailable: ' + pattern)
    return matches[0]


def spawn_scene(world, scene, transform_factory):
    """Create the sign, bicycle and one persistent human operator.

    transform_factory(x,y,z,yaw) is injected so CPU tests can check actual calls.
    The no-U-turn sign graphic/authorization must be confirmed locally; a traffic
    cone is deliberately rejected as a sign so this draft never claims readiness.
    """
    library = world.get_blueprint_library()
    sign = scene['sign']
    if not sign['blueprint_filter'].startswith('static.prop.sign'):
        raise ValueError('configured object is not a prohibition sign blueprint')
    sign_actor = world.spawn_actor(choose_blueprint(library, sign['blueprint_filter']),
                                   transform_factory(sign['x_m'], sign['y_m'], 0.0, sign['yaw_deg']))
    bike_actor = world.spawn_actor(choose_blueprint(library, scene['bicycle']['blueprint_filter']),
                                   transform_factory(scene['approach_x_m'], -scene['alley_half_width_m']/2, 0.0, 0.0))
    operator = world.spawn_actor(choose_blueprint(library, scene['operator']['blueprint_filter']),
                                 transform_factory(scene['approach_x_m'], -scene['alley_half_width_m']/2, 0.0, 0.0))
    return {'sign': sign_actor, 'bicycle': bike_actor, 'operator': operator}


def phase_at(scene, x_m, elapsed_since_dismount_s):
    if not scene['dismount_enabled']:
        return 'mounted_approach' if x_m < scene['dismount_x_m'] else 'mounted_reversal'
    if x_m < scene['dismount_x_m']:
        return 'mounted_approach'
    if elapsed_since_dismount_s < scene['control']['dismount_hold_s']:
        return 'dismount_hold'
    return 'afoot_reversal'


def check():
    scene = load_scene()
    points = path_points(scene)
    if scene['dismount_enabled']:
        assert points['mounted'][-1] == points['afoot'][0]
        assert phase_at(scene, scene['turn_x_m'], 0) == 'dismount_hold'
        assert phase_at(scene, scene['turn_x_m'], scene['control']['dismount_hold_s']) == 'afoot_reversal'
    else:
        assert not points['afoot']
        assert phase_at(scene, scene['turn_x_m'], 0) == 'mounted_reversal'
    print(json.dumps({'geometry_checked': True, 'sign_blueprint_unverified': scene['sign']['blueprint_filter']}))


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
        raise SystemExit('Native execution/capture is unfinished for this partial construction')


if __name__ == '__main__':
    main()
