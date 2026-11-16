"""Road-half scene variants and original body position for NRS 484B.200(1)."""
from __future__ import annotations
import hashlib
import json
from math import hypot,isfinite
from pathlib import Path

EXCEPTIONS=('none','overtaking_same_direction','right_half_closed','three_lanes','posted_one_way','insufficient_width')

class NativeRoadHalfAdapter:
    """CARLA-facing site adapter. Construction fails if the loaded road differs.

    The caller owns world synchronization, sensors, capture and finally cleanup.
    Site lane IDs and assets are authored engineering requests; map and actor
    readback below are retained by the later runner as original sources.
    """
    def __init__(self,world,carla,site):
        self.world,self.carla,self.site=world,carla,site
        self.actors=[]
        self.survey=None

    def _waypoint(self,lane_id,s):
        waypoint=self.world.get_map().get_waypoint_xodr(self.site['road_id'],lane_id,s)
        if waypoint is None or waypoint.road_id!=self.site['road_id'] or waypoint.lane_id!=lane_id:
            raise ValueError('loaded Native road/lane waypoint missing')
        if getattr(waypoint,'lane_type',None)!=self.carla.LaneType.Driving:
            raise ValueError('loaded Native waypoint is not a driving lane')
        if not 1.5<=float(waypoint.lane_width)<=6.0:
            raise ValueError('loaded Native lane width unmeasurable')
        return waypoint

    def road(self,*,layout,lanes,width_m,one_way):
        if layout!='intersection':raise ValueError('fixed C111250 layout changed')
        lane_ids=self.site['lane_ids']
        if len(lane_ids)!=lanes or len(set(lane_ids))!=lanes:
            raise ValueError('loaded Native lane count differs from exact case')
        stations=self.site['sample_s_m']
        if len(stations)<2 or sorted(stations)!=stations or stations[0]==stations[-1]:
            raise ValueError('Native road survey stations missing')
        # Count the reachable same-road driving lanes from the loaded map. An
        # authored lane-id list alone cannot establish three-lane geometry.
        seen={}
        pending=[self._waypoint(lane_ids[0],stations[0])]
        while pending:
            waypoint=pending.pop()
            if waypoint.lane_id in seen:continue
            seen[waypoint.lane_id]=waypoint
            if len(seen)>12:raise ValueError('Native road adjacency survey did not terminate')
            for accessor in ('get_left_lane','get_right_lane'):
                adjacent=getattr(waypoint,accessor)()
                if (adjacent is not None and adjacent.road_id==self.site['road_id']
                        and adjacent.lane_type==self.carla.LaneType.Driving):
                    pending.append(adjacent)
        if set(seen)!=set(lane_ids):raise ValueError('loaded Native adjacent driving-lane inventory differs')
        rows=[]
        for s in stations:
            for lane_id in lane_ids:
                waypoint=self._waypoint(lane_id,s)
                rows.append({'road_id':waypoint.road_id,'lane_id':waypoint.lane_id,
                             's_m':float(s),'lane_width_m':float(waypoint.lane_width),
                             'position_xy_m':[float(waypoint.transform.location.x),
                                              float(waypoint.transform.location.y)],
                             'heading_deg':float(waypoint.transform.rotation.yaw)})
        totals=[sum(row['lane_width_m'] for row in rows if row['s_m']==float(s)) for s in stations]
        if any(abs(total-width_m)>float(self.site.get('width_tolerance_m',.5)) for total in totals):
            raise ValueError('loaded Native road width differs from authored engineering request')
        if one_way and len({1 if lane_id>0 else -1 for lane_id in lane_ids})!=1:
            raise ValueError('loaded Native driving lanes are not same-direction')
        self.survey={'road_id':self.site['road_id'],'lane_count':lanes,
                     'sample_s_m':[float(s) for s in stations],'total_width_m':totals,
                     'one_way_lane_direction_readback':one_way,'lanes':rows,
                     'native_readback':True}
        return self.survey

    def _spawn(self,blueprint_key,lane_id,s,role):
        asset=self.site['blueprints'][blueprint_key]
        blueprint=self.world.get_blueprint_library().find(asset)
        if blueprint is None:raise ValueError('Native requested asset unavailable: '+asset)
        transform=self._waypoint(lane_id,s).transform
        transform.location.z+=float(self.site.get('spawn_height_offset_m',.3))
        actor=self.world.try_spawn_actor(blueprint,transform)
        if actor is None:raise ValueError('Native actor spawn failed: '+role)
        self.actors.append(actor)
        return {'role':role,'actor':actor,'actor_id':actor.id,'blueprint_id':asset,
                'road_id':self.site['road_id'],'lane_id':lane_id,'s_m':float(s),
                'native_readback':True}

    def vehicle(self,*,role,route,target_mps):
        if role not in ('ego','passed_vehicle') or len(route)!=2 or target_mps<=0:
            raise ValueError('Native subject/route request invalid')
        side='left' if route[0][1]>0 else 'right'
        key='ego_'+side+'_lane_id' if role=='ego' else 'passed_vehicle_lane_id'
        lane_id=self.site[key]
        row=self._spawn(role,lane_id,self.site['spawn_s_m'][role],role)
        row['target_mps']=float(target_mps)
        row['route_s_m']=[float(s) for s in self.site['route_s_m'][role]]
        if row['route_s_m'][-1]<=row['route_s_m'][0]:raise ValueError('Native route does not progress')
        for s in row['route_s_m']:self._waypoint(lane_id,s)
        return row

    def closure(self,*,road,side,begin_m,end_m):
        if road is not self.survey or side!='right' or end_m<=begin_m:
            raise ValueError('Native right-half closure request invalid')
        lane_id=self.site['ego_right_lane_id']
        stations=self.site['closure_s_m']
        origin=float(self.site['s_origin_m'])
        if not stations or min(stations)-origin>begin_m or max(stations)-origin<end_m:
            raise ValueError('Native closure placement does not cover requested interval')
        return {'role':'right_half_closure','road_id':self.site['road_id'],
                'native_readback':[self._spawn('barrier',lane_id,s,'barrier') for s in stations]}

    def sign(self,*,type,road):
        if type!='one_way' or road is not self.survey:
            raise ValueError('Native one-way sign request invalid')
        asset=self.site['blueprints']['one_way_sign']
        if 'oneway' not in asset.replace('_','').replace('-','').lower():
            raise ValueError('Native asset does not identify a one-way sign')
        row=self._spawn('one_way_sign',self.site['ego_right_lane_id'],
                        self.site['one_way_sign_s_m'],'one_way_sign')
        return {'role':'one_way_sign','road_id':self.site['road_id'],'native_readback':row}

    def close(self):
        for actor in reversed(self.actors):actor.destroy()
        self.actors.clear()

def construct(adapter,exception,body_side):
    if exception not in EXCEPTIONS or body_side not in ('right','left'):
        raise ValueError('unknown exact road-half variant')
    lanes=3 if exception=='three_lanes' else (1 if exception=='posted_one_way' else 2)
    # Engineering site widths are survey targets, not statutory definitions.
    width={'insufficient_width':3.0,'posted_one_way':3.5,'three_lanes':10.5}.get(exception,7.0)
    road=adapter.road(layout='intersection',lanes=lanes,width_m=width,one_way=exception=='posted_one_way')
    features=[]
    if exception=='overtaking_same_direction':
        features.append(adapter.vehicle(role='passed_vehicle',route=[(-20,-1),(20,-1)],target_mps=2))
    if exception=='right_half_closed':
        features.append(adapter.closure(road=road,side='right',begin_m=-10,end_m=10))
    if exception=='posted_one_way':
        features.append(adapter.sign(type='one_way',road=road))
    ego=adapter.vehicle(role='ego',route=[(-25,1 if body_side=='left' else -1),(25,1 if body_side=='left' else -1)],target_mps=4)
    return {'road':road,'features':features,'ego':ego}

def _signed(point,line):
    if (not isinstance(point,(list,tuple)) or len(point)!=2 or
            any(type(v) not in (int,float) or not isfinite(v) for v in point)):
        raise ValueError('original finite ground-corner coordinate missing')
    a,b=line;dx,dy=b[0]-a[0],b[1]-a[1];d=hypot(dx,dy)
    if d<1:raise ValueError('degenerate original road centerline')
    return (dx*(point[1]-a[1])-dy*(point[0]-a[0]))/d

def measure(context,frames):
    if context.get('exception') not in EXCEPTIONS or not context.get('exception_source') or not context.get('road_source'):
        raise ValueError('sourced road exception premise missing')
    line=context.get('centerline')
    if not isinstance(line,list) or len(line)!=2:raise ValueError('original road centerline missing')
    for point in line:
        if not isinstance(point,list) or len(point)!=2 or any(type(v) not in (int,float) or not isfinite(v) for v in point):
            raise ValueError('original finite road centerline missing')
    if not isinstance(frames,list) or len(frames)<2:raise ValueError('original body frames missing')
    right_sign=context.get('right_half_sign',-1)
    if right_sign not in (-1,1):raise ValueError('original road direction/right-half orientation missing')
    rows=[]
    for i,f in enumerate(frames):
        if f.get('frame')!=i or not f.get('body_source'):
            raise ValueError('original body frame or source missing')
        corners=f.get('ground_corners')
        if not isinstance(corners,list) or len(corners)!=4:raise ValueError('four original body corners required')
        sides=[_signed(p,line)*-right_sign for p in corners]
        rows.append({'frame':i,'min_leftward_m':min(sides),'max_leftward_m':max(sides),
                     'any_left_half_body':max(sides)>0,'whole_left_half_body':min(sides)>0})
    return {'exception':context['exception'],'right_half_sign':right_sign,
            'min_leftward_m':min(r['min_leftward_m'] for r in rows),
            'max_leftward_m':max(r['max_leftward_m'] for r in rows),
            'any_left_half_body':any(r['any_left_half_body'] for r in rows),
            'whole_left_half_frames':[r['frame'] for r in rows if r['whole_left_half_body']],
            'samples':rows,'legal_exception_judgment':None}

def _source(root,name):
    path=Path(root)/name
    data=path.read_bytes()
    return data,hashlib.sha256(data).hexdigest()

def measure_saved(root, *, expected_frames=None):
    """Measure full body/road-half occupancy from retained original sources only.

    Source context is a physical premise or site survey, never a legal permission.
    The frame map supplies acquisition identities; no fixture label or precomputed
    channel is accepted as a substitute for original body vertices.
    """
    road_data,road_sha=_source(root,'road_geometry.json')
    context_data,context_sha=_source(root,'exception_context.json')
    body_data,body_sha=_source(root,'body_history.jsonl')
    mapping_data,mapping_sha=_source(root,'video_frames.jsonl')
    road=json.loads(road_data)
    context=json.loads(context_data)
    body=[json.loads(s) for s in body_data.splitlines() if s.strip()]
    mapping=[json.loads(s) for s in mapping_data.splitlines() if s.strip()]
    if len(body)<2 or len(mapping)!=len(body):raise ValueError('original body/frame inventory incomplete')
    if expected_frames is not None and len(body)!=expected_frames:raise ValueError('planned duration/frame count incomplete')
    ids=[row.get('carla_frame') for row in mapping]
    times=[row.get('time_s') for row in mapping]
    if any(type(f) is not int for f in ids) or len(set(ids))!=len(ids) or any(b<=a for a,b in zip(ids,ids[1:])):
        raise ValueError('original frame identities missing or unordered')
    if any(type(t) not in (int,float) for t in times) or any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError('original frame timestamps missing or unordered')
    if any(row.get('frame')!=frame or row.get('time_s')!=time for row,frame,time in zip(body,ids,times)):
        raise ValueError('original body/frame identity join failed')
    if context.get('road_sha256')!=road_sha:raise ValueError('exception premise road source hash differs')
    feature=context.get('feature')
    required={'none':None,'overtaking_same_direction':'passed_vehicle',
              'right_half_closed':'physical_right_half_closure',
              'three_lanes':'surveyed_three_lane_geometry',
              'posted_one_way':'surveyed_one_way_sign',
              'insufficient_width':'surveyed_width'}
    exception=context.get('exception')
    if exception not in required or feature!=required[exception]:raise ValueError('exception feature source is incomplete')
    if road.get('road_id')!=context.get('road_id') or not road.get('survey_source'):
        raise ValueError('original road/site source linkage missing')
    if exception=='three_lanes' and road.get('lane_count')!=3:raise ValueError('original three-lane survey differs')
    extra={'posted_one_way':('one_way_sign_original.json','sign_source_sha256'),
           'right_half_closed':('closure_original.json','closure_source_sha256'),
           'overtaking_same_direction':('passed_vehicle_original.json','passed_vehicle_source_sha256'),
           'insufficient_width':('width_survey_original.json','width_survey_source_sha256'),
           'three_lanes':('lane_survey_original.json','lane_survey_source_sha256')}
    feature_source={}
    if exception in extra:
        feature_name,hash_key=extra[exception]
        try:feature_data,feature_sha=_source(root,feature_name)
        except FileNotFoundError as error:raise ValueError('original exception feature source missing: '+feature_name) from error
        if context.get(hash_key)!=feature_sha:raise ValueError('original exception feature source hash differs: '+feature_name)
        feature_source[feature_name]=feature_sha
        feature_readback=json.loads(feature_data)
        if feature_readback.get('road_id')!=road['road_id'] or not feature_readback.get('native_readback'):
            raise ValueError('original exception feature site/readback missing: '+feature_name)
        if exception=='three_lanes' and feature_readback.get('lane_count')!=3:
            raise ValueError('original three-lane feature survey differs')
    source_context={'exception':exception,'exception_source':context_sha,'road_source':road_sha,
                    'centerline':road.get('centerline'),'right_half_sign':road.get('right_half_sign')}
    samples=[{'frame':i,'body_source':body_sha,'ground_corners':row.get('ground_corners')}
             for i,row in enumerate(body)]
    result=measure(source_context,samples)
    result['source_sha256']={'road_geometry.json':road_sha,'exception_context.json':context_sha,
                             'body_history.jsonl':body_sha,'video_frames.jsonl':mapping_sha,**feature_source}
    result['original_frames']=ids
    result['original_times_s']=times
    result['physical_premise_confirmed']=False
    return result

def audit_comparison(a,b,variable):
    if variable not in ('body_side','exception_premise') or not a.get('samples') or not b.get('samples'):
        raise ValueError('original two-case road-half measurements required')
    keys=('road_hash','centerline_hash','camera_plan_hash','duration_s','actor_hash') if variable=='body_side' else ('centerline_hash','camera_plan_hash','duration_s','actor_hash')
    for key in keys:
        if not a.get(key) or a[key]!=b.get(key):raise ValueError('fixed condition changed: '+key)
    for result in (a,b):
        if result.get('any_left_half_body')!=any(s.get('max_leftward_m',0)>0 for s in result['samples']):
            raise ValueError('derived body side differs from original samples')
    fixed,varied=('exception','any_left_half_body') if variable=='body_side' else ('any_left_half_body','exception')
    if a.get(fixed)!=b.get(fixed):raise ValueError('held condition changed: '+fixed)
    if a.get(varied)==b.get(varied):raise ValueError('deliberate difference absent')
    return {'comparison_complete':True,'legal_exception_judgment':None}
