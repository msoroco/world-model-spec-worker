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
    if not (0<scene['arrow_exhibition_after_s']<scene['duration_s']):
        raise ValueError('arrow exhibition schedule outside capture')
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
        body_bounds(item['body_vertices_m'])
        within=any(overlaps(item['body_vertices_m'],r) for r in regions)
        if within and (type(item['lawfully_present']) is not bool or not item['lawful_presence_source']):
            raise ValueError('lawful presence source missing for governed-region occupant')
        if within and item['lawfully_present']:
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


def control_step(scene, signal, participants, ego_vertices, *, first_arrow_frame=None,
                 exhibition_occupants=None):
    """Decide the next Native control from the latest original frame.

    Unknown source facts fail closed. The initial control is a full brake until
    the first observed frame is available; this decision controls the next tick.
    """
    frame=signal.get('frame')
    if type(frame) is not int:
        raise ValueError('original signal frame missing')
    hold={'throttle':0.0,'brake':1.0,'steer':0.0,'intended_maneuver':'straight'}
    try:
        require_sole_straight_arrow(signal['aspect'],
                                   head_id=signal['facing_head_id'],frame=frame)
    except (KeyError,ValueError) as exc:
        return {'control':hold,'reason':'unverified_sole_arrow',
                'source_error':str(exc),'first_arrow_frame':first_arrow_frame,
                'exhibition_occupants':exhibition_occupants}
    if first_arrow_frame is None:
        first_arrow_frame=frame
        try:
            first=yield_decision(scene,participants,
                                 signal_exhibited_frame=frame,current_frame=frame)
            exhibition_occupants=first['occupied_by']
        except ValueError as exc:
            return {'control':hold,'reason':'unverified_exhibition_lawfulness',
                    'source_error':str(exc),'first_arrow_frame':frame,
                    'exhibition_occupants':None}
    if exhibition_occupants is None:
        return {'control':hold,'reason':'unverified_exhibition_lawfulness',
                'source_error':'lawful presence at original exhibition frame was unverified',
                'first_arrow_frame':first_arrow_frame,'exhibition_occupants':None}
    regions=[scene['intersection_bounds_m'],*scene['adjacent_crosswalk_bounds_m']]
    occupants={item['id']:item for item in participants}
    missing=[ident for ident in exhibition_occupants if ident not in occupants]
    if missing:
        return {'control':hold,'reason':'missing_exhibition_occupant_body',
                'source_error':'original body no longer available: '+str(missing),
                'first_arrow_frame':first_arrow_frame,
                'exhibition_occupants':exhibition_occupants}
    try:
        remaining=[ident for ident in exhibition_occupants if any(
            overlaps(occupants[ident]['body_vertices_m'],region) for region in regions)]
        front=body_bounds(ego_vertices)[2]
        control=command(scene,front,{'hold_at_stop_line':bool(remaining)})
    except ValueError as exc:
        return {'control':hold,'reason':'unverified_lawful_presence_or_geometry',
                'source_error':str(exc),'first_arrow_frame':first_arrow_frame,
                'exhibition_occupants':exhibition_occupants}
    return {'control':control,'reason':'yield_hold' if remaining else 'straight_clear',
            'occupied_by':remaining,'first_arrow_frame':first_arrow_frame,
            'exhibition_occupants':exhibition_occupants}


def spawn_scene(world,scene,transform_factory):
    """Create distinct ego, vehicle and pedestrian actors for the exact case.

    The occupied case starts both participants outside the governed regions, so
    original capture can observe their entry before arrow exhibition.
    """
    library=world.get_blueprint_library()
    specs=[('ego','vehicle.*',scene['approach_x_m'],0,0),
           ('vehicle','vehicle.*',0 if scene['participant_occupancy_setup']=='lawfully_present' else 35,
            -12 if scene['participant_occupancy_setup']=='lawfully_present' else 0,90),
           ('pedestrian','walker.pedestrian.*',9 if scene['participant_occupancy_setup']=='lawfully_present' else 35,
            -9 if scene['participant_occupancy_setup']=='lawfully_present' else 0,90)]
    if scene['participant_occupancy_setup'] not in ('clear','lawfully_present'):
        raise ValueError('unsupported occupancy setup')
    actors={}
    try:
        for name,pattern,x,y,yaw in specs:
            matches=list(library.filter(pattern))
            if not matches:raise ValueError('missing Native actor blueprint: '+pattern)
            actors[name]=world.spawn_actor(matches[0],transform_factory(x,y,0,yaw))
        if len({id(actor) for actor in actors.values()})!=len(actors):
            raise ValueError('Native world reused an actor for distinct roles')
    except BaseException:
        for actor in reversed(list(actors.values())):
            if hasattr(actor,'destroy'):actor.destroy()
        raise
    return actors


def authored_arrow_state(scene,elapsed_s):
    """Predeclared Red-to-Green stimulus; original readback controls inference."""
    if type(elapsed_s) not in (int,float) or not math.isfinite(elapsed_s) or elapsed_s<0:
        raise ValueError('invalid arrow schedule time')
    return 'Red' if elapsed_s<scene['arrow_exhibition_after_s'] else 'Green'


def participant_motion(scene, elapsed_s):
    """Native control targets that clear both governed regions after a hold.

    The vehicle crosses northbound through the intersection; the pedestrian
    crosses the adjacent crosswalk. This is a construction policy only. Body
    positions and lawful presence must still be read back from original sources.
    """
    if type(elapsed_s) not in (int,float) or not math.isfinite(elapsed_s) or elapsed_s<0:
        raise ValueError('invalid participant elapsed time')
    if scene['participant_occupancy_setup']=='clear':
        return {'vehicle_velocity_xyz_mps':(0.,0.,0.),
                'pedestrian_direction_xyz':(0.,0.,0.),'pedestrian_speed_mps':0.}
    if scene['participant_occupancy_setup']!='lawfully_present':
        raise ValueError('unsupported occupancy setup')
    # The target motion moves bodies beyond the y=5 m region boundary within
    # the 30 s capture. A Native controller must stop them after readback clears.
    return {'vehicle_velocity_xyz_mps':(0.,2.,0.),
            'pedestrian_direction_xyz':(0.,1.,0.),'pedestrian_speed_mps':1.5}


def apply_participant_motion(scene, actors, carla, elapsed_s):
    """Issue the occupied/clear construction controls to owned Native actors."""
    motion=participant_motion(scene,elapsed_s)
    vx,vy,vz=motion['vehicle_velocity_xyz_mps']
    dx,dy,dz=motion['pedestrian_direction_xyz']
    actors['vehicle'].set_target_velocity(carla.Vector3D(x=vx,y=vy,z=vz))
    actors['pedestrian'].apply_control(carla.WalkerControl(
        direction=carla.Vector3D(x=dx,y=dy,z=dz),speed=motion['pedestrian_speed_mps']))
    return motion


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
    from native_capture import run_native
    run_native(load_scene(),args.output_dir,args.host,args.port)


if __name__=='__main__':main()
