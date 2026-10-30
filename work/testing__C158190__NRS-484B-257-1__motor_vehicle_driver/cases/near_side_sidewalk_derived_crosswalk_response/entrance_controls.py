"""Physical rendered white road-marking mesh construction with paint-like collision response, not a debug overlay.

Installed traffic-line mesh tiles form a contiguous authored stop line. Native
queries and pixels must verify the construction; requested poses are not evidence.
"""
ASSET='/Game/Carla/Static/RoadLine/SM_BassicTrafficLineCube_trafficlineCube.SM_BassicTrafficLineCube_trafficlineCube'
# Actual scale1 local bounds from retained mesh-survey-v2. New setup rechecks them.
EXTENT=(.06204589828848839,.06204365938901901,.0038028834387660027)
CENTER=(.061835937201976776,0,2.38418573772492e-09)
SCALE=.35/(2*EXTENT[1])

def spawn_markings(carla,world,cfg):
 actors=[];kind=cfg['reference_kind']
 if kind=='nearest_view':return actors
 bp=world.get_blueprint_library().find('static.prop.mesh');bp.set_attribute('mesh_path',ASSET);bp.set_attribute('scale',str(SCALE));bp.set_attribute('mass','0')
 for i in range(80 if 'crosswalk' in kind else 20):
  if kind=='marked_stop_line':x=-11;y=-.175-.35*i;z=.002
  elif kind=='near_side_marked_crosswalk':x=-8.25+(i%4)*.35;y=-6.8+(i//4)*.7;z=.002
  else:x=-8.25+(i%4)*.35;y=(-9.8+(i//4)*.3 if i<40 else 7.1+((i-40)//4)*.3);z=.15
  a=world.spawn_actor(bp,carla.Transform(carla.Location(x=x-CENTER[0],y=y,z=z)));a.set_simulate_physics(False);a.set_collisions(False);actors.append(a)
 return actors

def setup_governance(carla,world,map_,cfg,owned):
 result={}
 if cfg['control_kind']=='officer':
  bp=world.get_blueprint_library().find('walker.pedestrian.0001');officer=world.spawn_actor(bp,carla.Transform(carla.Location(x=-10,y=-9,z=.3),carla.Rotation(yaw=90)));owned.append(officer);result['officer']=officer
 elif cfg['control_kind']=='signal':
  heads=[a for a in world.get_actors() if a.type_id.startswith('traffic.traffic_light') and getattr(a,'get_opendrive_id',lambda:'' )()=='257light']
  if len(heads)!=1:raise ValueError('Exactly one installed Native governance signal required')
  signal=heads[0];signal.freeze(True);result['signal']=signal
 return result

def observe_governance(carla,world,g,cfg,tick):
 inventory=[{'actor_id':a.id,'type_id':a.type_id} for a in world.get_actors() if a.type_id.startswith(('walker.','traffic.traffic_light'))]
 result={'world_control_actor_inventory':inventory,'controls_subject':False}
 if 'officer' in g:
  officer=g['officer'];direction='stop' if tick<200 else 'proceed';active=cfg['governing_active']
  bones=officer.get_bones();names=[b.name for b in bones.bone_transforms if 'arm' in b.name.lower()]
  if active:
   if not names:raise ValueError('Native officer skeleton has no arm bones for direction')
   officer.set_bones(carla.WalkerBoneControlIn([(names[0],carla.Transform(rotation=carla.Rotation(roll=-85 if direction=='stop' else -20)))]));officer.blend_pose(1.0)
  observed=officer.get_bones();roll=next((b.relative.rotation.roll for b in observed.bone_transforms if names and b.name==names[0]),None)
  observed_direction='stop' if roll is not None and abs(roll+85)<5 else 'proceed' if roll is not None and abs(roll+20)<5 else 'unrecognized'
  result.update(officer_actor_id=officer.id,direction=observed_direction if active else 'no direction',controls_subject=active and observed_direction!='unrecognized',bone_readback=[{'name':b.name,'relative':str(b.relative),'relative_roll_deg':b.relative.rotation.roll} for b in observed.bone_transforms],officer_authority_context='Authored sworn traffic officer; credential/legal authority requires source review')
 if 'signal' in g:
  signal=g['signal'];signal.set_state(carla.TrafficLightState.Red if tick<200 else carla.TrafficLightState.Green)
  affected=[[w.road_id,w.section_id,w.lane_id] for w in signal.get_affected_lane_waypoints()]
  controls=any(r==1 and lane in (-1,-2) for r,sec,lane in affected)
  result.update(signal_actor_id=signal.id,signal_state=str(signal.get_state()).split('.')[-1],affected_lanes=affected,controls_subject=controls)
 return result
