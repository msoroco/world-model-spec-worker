"""Physical rendered white road-marking mesh construction with paint-like collision response, not a debug overlay.

Installed traffic-line mesh tiles form a contiguous authored stop line. Native
queries and pixels must verify the construction; requested poses are not evidence.
"""
ASSET='/Game/Carla/Static/RoadLine/SM_BassicTrafficLineCube_trafficlineCube.SM_BassicTrafficLineCube_trafficlineCube'
# Actual scale1 local bounds from retained mesh-survey-v2. New setup rechecks them.
EXTENT=(.06204589828848839,.06204365938901901,.0038028834387660027)
CENTER=(.061835937201976776,0,2.38418573772492e-09)
SCALE=.35/(2*EXTENT[1])

def spawn(carla,world,include_west):
 bp=world.get_blueprint_library().find('static.prop.mesh')
 bp.set_attribute('mesh_path',ASSET);bp.set_attribute('scale',str(SCALE));bp.set_attribute('mass','0');actors=[]
 for side,x,sign in ([('west',-11,1)] if include_west else []):
  for i in range(20):
   y=sign*(.175+.35*i);bp.set_attribute('role_name','stop257_'+side+'_physical_stopline_tile_%02d'%i)
   pose=carla.Transform(carla.Location(x=x-CENTER[0],y=y,z=.002-EXTENT[2]*SCALE-CENTER[2]))
   actor=world.spawn_actor(bp,pose);actor.set_simulate_physics(False);actor.set_collisions(False);actors.append(actor)
 return actors

def observe(actors):
 values=[]
 for actor in actors:
  t=actor.get_transform();b=actor.bounding_box
  values.append({'actor_id':actor.id,'blueprint':actor.type_id,'role':actor.attributes.get('role_name'),'asset':actor.attributes.get('mesh_path'),'scale':actor.attributes.get('scale'),'native_transform':str(t),'native_matrix':t.get_matrix(),'position_m':[t.location.x,t.location.y,t.location.z],'body_vertices_m':[[p.x,p.y,p.z] for p in b.get_world_vertices(t)],'bbox_extent_m':[b.extent.x,b.extent.y,b.extent.z],'bbox_local_center_m':[b.location.x,b.location.y,b.location.z]})
 return values
