"""Physical rendered white road-marking mesh construction with paint-like collision response, not a debug overlay.

Installed traffic-line mesh tiles form a contiguous authored stop line. Native
queries and pixels must verify the construction; requested poses are not evidence.
"""
ASSET='/Game/Carla/Static/RoadLine/SM_BassicTrafficLineCube_trafficlineCube.SM_BassicTrafficLineCube_trafficlineCube'
# Actual scale1 local bounds from retained mesh-survey-v2. New setup rechecks them.
EXTENT=(.06204589828848839,.06204365938901901,.0038028834387660027)
CENTER=(.061835937201976776,0,2.38418573772492e-09)
SCALE=.35/(2*EXTENT[1])

def spawn(carla,world,cfg):
 actors=[]
 bp=world.get_blueprint_library().find('static.prop.mesh');bp.set_attribute('mesh_path',ASSET);bp.set_attribute('scale',str(SCALE));bp.set_attribute('mass','0')
 mode=cfg['stop_reference']
 if mode=='marked_crosswalk':xs=[-13+i*.35 for i in range(9)]
 elif mode=='stop_line':xs=[-11]
 else:xs=[]
 for x in xs:
  for i in range(20):
   bp.set_attribute('role_name','statutory_'+mode+'_tile')
   actor=world.spawn_actor(bp,carla.Transform(carla.Location(x=x-CENTER[0],y=.175+.35*i,z=.002-EXTENT[2]*SCALE-CENTER[2])))
   actor.set_simulate_physics(False);actor.set_collisions(False);actors.append(actor)
 return actors

def observe(actors):
 return [{'actor_id':a.id,'body_vertices_m':[[v.x,v.y,v.z] for v in a.bounding_box.get_world_vertices(a.get_transform())]} for a in actors]
