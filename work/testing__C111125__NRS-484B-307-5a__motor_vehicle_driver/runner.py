"""NRS 484B.307(5)(a) straight-arrow controller and source guards.

CARLA's generic green state does not identify an arrow indication. Native
capture must supply a verified signal-head description before any attempt.
"""
import argparse
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def load_scene(path=None):
    scene=json.loads(Path(path or ROOT/'scene.json').read_text())
    if (scene['law_id'],scene['cell_id'],scene['actor']) != (
            'NRS-484B-307-5a','C111125','motor_vehicle_driver'):
        raise ValueError('wrong frozen assignment identity')
    if scene['approach_x_m']>=scene['stop_line_x_m'] or scene['exit_x_m']<=scene['intersection_x_max_m']:
        raise ValueError('straight route must approach stop line and clear intersection')
    if scene['intersection_x_min_m']>=scene['intersection_x_max_m']:
        raise ValueError('invalid intersection bounds')
    return scene


def require_sole_straight_arrow(signal, *, head_id, frame):
    """Read back one source-verified facing head; reject a generic green bulb."""
    if signal.get('source_verified') is not True or not signal.get('source_ref'):
        raise ValueError('sole arrow lacks source-verified signal head')
    if signal.get('head_id')!=head_id or signal.get('observed_frame')!=frame:
        raise ValueError('signal aspect is not bound to the facing head and frame')
    indications=signal.get('illuminated_indications')
    if indications!=[{'color':'green','shape':'arrow','direction':'straight'}]:
        raise ValueError('facing signal is not a sole green straight-through arrow')
    return signal


def select_facing_head(scene, heads, *, frame):
    """Select a source-verified facing arrow head by a predeclared slot.

    The alternate slot is engineering redundancy, never an outcome selector.
    A Native adapter must populate heads from original per-frame signal sources.
    """
    slot=scene.get('candidate_head_slot',0)
    if type(slot) is not int or slot<0:
        raise ValueError('invalid predeclared head slot')
    facing=[head for head in heads if head.get('faces_ego_approach') is True]
    if any(type(head.get('head_id')) is not int for head in facing):
        raise ValueError('facing signal head lacks stable integer ID')
    facing.sort(key=lambda head:head['head_id'])
    if len({head['head_id'] for head in facing})!=len(facing):
        raise ValueError('duplicate facing signal head ID')
    if slot>=len(facing):
        raise ValueError('selected facing signal head slot absent')
    chosen=facing[slot]
    return require_sole_straight_arrow(chosen,head_id=chosen['head_id'],frame=frame)


def body_bounds(vertices):
    if not isinstance(vertices,list) or len(vertices)<4 or any(
            not isinstance(v,list) or len(v)<2 or
            any(type(x) not in (int,float) or not math.isfinite(x) for x in v[:2])
            for v in vertices):
        raise ValueError('missing finite participant body footprint')
    return (min(v[0] for v in vertices),min(v[1] for v in vertices),
            max(v[0] for v in vertices),max(v[1] for v in vertices))


def overlaps(vertices,region):
    left,bottom,right,top=body_bounds(vertices)
    if len(region)!=4 or any(type(x) not in (int,float) or not math.isfinite(x) for x in region):
        raise ValueError('invalid intersection or crosswalk bounds')
    a,b,c,d=region
    if a>=c or b>=d:raise ValueError('invalid region bounds')
    return left<=c and right>=a and bottom<=d and top>=b


def yield_decision(scene, participants, *, signal_exhibited_frame, current_frame):
    """Hold at the line while a lawfully present participant still occupies it.

    Lawful presence is an independently sourced input, never inferred from a
    pedestrian's or vehicle's position alone.
    """
    if current_frame<signal_exhibited_frame:raise ValueError('signal exhibition time is in the future')
    occupied=[]
    regions=[scene['intersection_bounds_m'],*scene['adjacent_crosswalk_bounds_m']]
    for item in participants:
        if not {'id','role','body_vertices_m','lawful_presence_source','lawfully_present'}<=item.keys():
            raise ValueError('participant lawfulness or body source missing')
        if item['role'] not in ('vehicle','pedestrian'):
            raise ValueError('unsupported participant role')
        if not item['lawful_presence_source']:
            raise ValueError('lawful presence source missing')
        body_bounds(item['body_vertices_m'])
        if item['lawfully_present'] and any(overlaps(item['body_vertices_m'],r) for r in regions):
            occupied.append(item['id'])
    return {'hold_at_stop_line':bool(occupied),'occupied_by':occupied,
            'signal_exhibited_frame':signal_exhibited_frame,'decision_frame':current_frame,
            'method':'original participant body overlap and independently sourced lawful presence'}


def command(scene, ego_front_x_m, decision):
    if not isinstance(decision,dict) or 'hold_at_stop_line' not in decision:
        raise ValueError('missing yield decision')
    if decision['hold_at_stop_line'] and ego_front_x_m>scene['stop_line_x_m']:
        raise ValueError('ego already crossed stop line before yield cleared')
    return {'throttle':0.0 if decision['hold_at_stop_line'] else .25,
            'brake':1.0 if decision['hold_at_stop_line'] else 0.0,
            'steer':0.0,'intended_maneuver':'straight'}


def spawn_scene(world,scene,transform_factory):
    """Create distinct ego, vehicle and pedestrian actors for the exact case.

    The occupied case places both participant classes in governed regions.
    Lawful presence still requires independent original phase/right-of-way source.
    """
    library=world.get_blueprint_library()
    specs=[('ego','vehicle.*',scene['approach_x_m'],0),
           ('vehicle','vehicle.*',0 if scene['participant_occupancy_setup']=='lawfully_present' else 35,0),
           ('pedestrian','walker.pedestrian.*',9 if scene['participant_occupancy_setup']=='lawfully_present' else 35,0)]
    if scene['participant_occupancy_setup'] not in ('clear','lawfully_present'):
        raise ValueError('unsupported occupancy setup')
    actors={}
    try:
        for name,pattern,x,y in specs:
            matches=list(library.filter(pattern))
            if not matches:raise ValueError('missing Native actor blueprint: '+pattern)
            actors[name]=world.spawn_actor(matches[0],transform_factory(x,y,0,0))
        if len({id(actor) for actor in actors.values()})!=len(actors):
            raise ValueError('Native world reused an actor for distinct roles')
    except BaseException:
        for actor in reversed(list(actors.values())):
            if hasattr(actor,'destroy'):actor.destroy()
        raise
    return actors


def check():
    scene=load_scene()
    assert scene['approach_x_m']<scene['stop_line_x_m']<scene['intersection_x_max_m']<scene['exit_x_m']
    heads=[{'source_verified':True,'source_ref':'synthetic/check-only',
            'head_id':head_id,'observed_frame':0,'faces_ego_approach':True,
            'illuminated_indications':[{'color':'green','shape':'arrow','direction':'straight'}]}
           for head_id in (7,8)]
    chosen=select_facing_head(scene,heads,frame=0)
    print(json.dumps({'geometry_checked':True,'selected_synthetic_head_id':chosen['head_id'],
                      'sole_arrow_source_verification_pending':True}))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args()
    if args.check:check();return
    if not args.output_dir:parser.error('--output-dir is required for Native capture')
    raise ValueError('Native signal-head source binding and capture remain under construction')


if __name__=='__main__':main()
