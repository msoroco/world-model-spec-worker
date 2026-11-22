"""NRS 484B.217(2) left-turn construction; CARLA loads only for Native runs."""
import argparse
import json
from pathlib import Path

SCENE = Path(__file__).with_name('scene.json')


def load_scene(path=SCENE):
    scene = json.loads(Path(path).read_text())
    if (scene['law_id'], scene['cell_id'], scene['actor']) != (
            'NRS-484B-217-2', 'C109755', 'motor_vehicle_driver'):
        raise ValueError('wrong frozen identity')
    if not scene['approach_lane_center_y_m'] < scene['stripe_y_m'] < scene['opposing_lane_center_y_m']:
        raise ValueError('striping is not between opposing lanes')
    if not scene['start_x_m'] < scene['signal_start_x_m'] < scene['crossing_x_m']-4:
        raise ValueError('signal station must precede stripe crossing')
    # A 300 foot approach covers the longer NRS 484B.413(2) district case.
    # Actual continuous signaling and traveled distance are measured from capture.
    if scene['crossing_x_m']-4-scene['signal_start_x_m'] < 300*0.3048:
        raise ValueError('authored signal approach is shorter than 300 feet')
    if scene['exit_y_m'] <= scene['opposing_lane_center_y_m']:
        raise ValueError('left-turn exit must cross the opposing side')
    return scene


def route(scene):
    y = scene['approach_lane_center_y_m']
    x = scene['crossing_x_m']
    return [(scene['start_x_m'], y), (scene['signal_start_x_m'], y),
            (x-3.0,y), (x,scene['stripe_y_m']), (x,scene['opposing_lane_center_y_m']),
            (x,scene['exit_y_m'])]


def crosses_stripe(scene):
    points = route(scene)
    return any(a[1] < scene['stripe_y_m'] <= b[1] for a,b in zip(points,points[1:]))


def require_marking(carla_map, location, expected='Solid'):
    waypoint = carla_map.get_waypoint(location)
    if waypoint is None:
        raise ValueError('map has no approach waypoint at stripe crossing')
    marking = getattr(waypoint, 'left_lane_marking', None)
    if marking is None or expected.lower() not in str(getattr(marking,'type','')).lower():
        raise ValueError('map lacks solid no-passing striping at crossing')
    return waypoint


def choose(library, pattern):
    matches = list(library.filter(pattern))
    if not matches:
        raise ValueError('required vehicle blueprint missing: '+pattern)
    return matches[0]


def spawn_scene(world, scene, transform_factory):
    """Create three distinct vehicles; caller retains ownership for cleanup."""
    library = world.get_blueprint_library()
    specs = [('ego','ego_blueprint',scene['start_x_m'],scene['approach_lane_center_y_m'],0),
             ('oncoming','oncoming_blueprint',scene['oncoming_start_x_m'],scene['opposing_lane_center_y_m'],180),
             ('following','following_blueprint',scene['following_start_x_m'],scene['approach_lane_center_y_m'],0)]
    actors={}
    try:
        for name,key,x,y,yaw in specs:
            actors[name] = world.spawn_actor(choose(library,scene[key]),transform_factory(x,y,0,yaw))
        if len({id(a) for a in actors.values()}) != len(actors):
            raise ValueError('world reused an actor for distinct traffic roles')
    except BaseException:
        for actor in reversed(list(actors.values())):
            if hasattr(actor,'destroy'):actor.destroy()
        raise
    return actors


def controller_command(scene, x_m, turn_started):
    signal = bool(scene['signal_enabled'] and x_m >= scene['signal_start_x_m'])
    return {'left_signal':signal,'steer':0.4 if turn_started else 0.0,
            'throttle':0.3 if not turn_started else 0.2,'brake':0.0}


def check():
    scene=load_scene()
    assert crosses_stripe(scene)
    assert route(scene)[0][1] < scene['stripe_y_m'] < route(scene)[-1][1]
    assert controller_command(scene,scene['signal_start_x_m']-1,False)['left_signal'] is False
    print(json.dumps({'geometry_checked':True,'map_marking_requires_native_verification':True}))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args()
    if args.check:check()
    else:
        if not args.output_dir:
            parser.error('--output-dir is required for Native capture')
        from native_capture import run_native
        run_native(load_scene(),Path(args.output_dir),args.host,args.port)


if __name__=='__main__':main()
