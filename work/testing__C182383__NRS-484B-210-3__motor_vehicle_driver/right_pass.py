"""Source-gated Native paved-edge pass corridor with separate actual and required facts."""
import math
from package_spec import AID
VARIANTS={'narrow_off_pavement':(False,True,True),'wide_on_pavement':(True,True,False),'wide_off_pavement':(True,True,True),'narrow_no_pass':(False,False,False)}
def number(v):
 if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError('finite numeric source fact required')
 return float(v)
def construct(site,case):
 suffix=case.removeprefix(AID+'__')
 if site.get('assignment_id')!=AID or site.get('case_id')!=case or suffix not in VARIANTS or site.get('source_kind')!='original_native_map_geometry' or site.get('reviewed_original_native_site') is not True:raise ValueError('exact reviewed Native paved-edge site required')
 for key in ('source_id','map_name','map_sha256','paved_surface_source','paved_boundary_source','connected_route_source','driver_actor_id','overtaken_actor_source'):
  if not site.get(key):raise ValueError('independent paved-edge/actor source missing: '+key)
 if site.get('public_highway') is not True or site.get('paved_surface_classified') is not True or site.get('adjacent_surface_classified') is not True:raise ValueError('public highway and classified paved/adjacent surfaces required')
 if site.get('map_lane_type_as_legal_pavement') is True:raise ValueError('map lane type cannot establish legal paved portion')
 fit,passed,off=VARIANTS[suffix]
 if (site.get('requested_zero_clearance_paved_fit'),site.get('requested_right_pass'),site.get('requested_off_pavement'))!=(fit,passed,off):raise ValueError('exact pass/pavement request differs')
 frame=site.get('road_frame')
 if not isinstance(frame,dict) or not frame.get('source_id') or any(not isinstance(frame.get(k),list) or len(frame[k])!=2 for k in ('origin_xy','station_axis_xy','left_axis_xy')):raise ValueError('source road frame required')
 for k in ('origin_xy','station_axis_xy','left_axis_xy'):
  for v in frame[k]:number(v)
 sections=site.get('cross_sections')
 if not isinstance(sections,list) or len(sections)<3:raise ValueError('continuous surveyed pass corridor required')
 stations=[]
 for section in sections:
  if section.get('source_kind')!='surveyed_original_native_pavement' or not section.get('source_ref') or section.get('connected_drivable_route') is not True:raise ValueError('source-surveyed connected paved/adjacent corridor required')
  stations.append(number(section.get('station_m')))
  lo,hi=section.get('paved_y_bounds_m',(None,None));number(lo);number(hi)
  if lo>=hi:raise ValueError('invalid paved bounds')
 if stations!=sorted(set(stations)) or stations[0]>-30 or stations[-1]<30 or max(b-a for a,b in zip(stations,stations[1:]))>5:raise ValueError('continuous 5m sampled corridor required')
 half=number(site.get('ego_body_half_width_m'));target_right=number(site.get('overtaken_right_edge_m'))
 if half<=0:raise ValueError('ego width required')
 available=min(section['paved_y_bounds_m'][1]-target_right for section in sections)
 observed_fit=available>=2*half
 if observed_fit is not fit:raise ValueError('requested zero-clearance body fit differs from surveyed width')
 control=site.get('variant_controls')
 if not isinstance(control,dict) or not control.get('source_id'):raise ValueError('source-backed variant controller required')
 for k in ('ego_speed_mps','target_speed_mps','ego_target_lateral_m'):number(control.get(k))
 if control['ego_speed_mps']<=0 or control['target_speed_mps']<=0 or (passed and control['ego_speed_mps']<=control['target_speed_mps']) or (not passed and control['ego_speed_mps']>control['target_speed_mps']):raise ValueError('source speeds cannot realize exact pass variant')
 lateral=control['ego_target_lateral_m'];paved_right=min(row['paved_y_bounds_m'][1] for row in sections)
 if passed and lateral-half<target_right:raise ValueError('right-side overtaking corridor absent')
 if off and lateral+half<=paved_right:raise ValueError('off-pavement target remains on pavement')
 if not off and lateral+half>paved_right:raise ValueError('on-pavement target crosses paved edge')
 spawn=site.get('native_spawn')
 if not isinstance(spawn,dict):raise ValueError('two source-backed Native poses required')
 for role in ('ego','target'):
  item=spawn.get(role)
  if not isinstance(item,dict) or not item.get('source_id') or not item.get('blueprint_id') or not isinstance(item.get('pose_xyz_ypr'),list) or len(item['pose_xyz_ypr'])!=6:raise ValueError('source-backed vehicle pose required: '+role)
  for v in item['pose_xyz_ypr']:number(v)
 return {'variant':suffix,'case_id':case,'ego_speed_mps':control['ego_speed_mps'],'target_speed_mps':control['target_speed_mps'],'ego_target_lateral_m':control['ego_target_lateral_m'],'expected_pass':passed,'expected_off_pavement':off,'zero_clearance_fit':fit,'native_readback_required':True}
def spawn_native(world,blueprints,site,request,transform_factory):
 actors={}
 try:
  for role in ('ego','target'):
   item=site['native_spawn'][role]
   actor=world.try_spawn_actor(blueprints.find(item['blueprint_id']),transform_factory(item['pose_xyz_ypr']))
   if actor is None or not getattr(actor,'id',None) or actor.get_transform() is None:raise ValueError('Native '+role+' spawn/readback failed')
   actors[role]=actor
  if actors['ego'].id==actors['target'].id:raise ValueError('distinct actor identities required')
  return actors
 except Exception:
  for actor in reversed(list(actors.values())):actor.destroy()
  raise
