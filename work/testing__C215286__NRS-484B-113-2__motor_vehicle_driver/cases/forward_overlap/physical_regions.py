"""Physical rendered white road-marking mesh construction with paint-like collision response, not a debug overlay.

Installed traffic-line mesh tiles form a contiguous authored stop line. Native
queries and pixels must verify the construction; requested poses are not evidence.
"""
ASSET='/Game/Carla/Static/RoadLine/SM_BassicTrafficLineCube_trafficlineCube.SM_BassicTrafficLineCube_trafficlineCube'
# Actual scale1 local bounds from retained mesh-survey-v2. New setup rechecks them.
EXTENT=(.06204589828848839,.06204365938901901,.0038028834387660027)
CENTER=(.061835937201976776,0,2.38418573772492e-09)
SCALE=.35/(2*EXTENT[1])

def spawn(carla,world,definition):
 actors=[];bp=world.get_blueprint_library().find('static.prop.mesh');bp.set_attribute('mesh_path',ASSET);bp.set_attribute('scale',str(SCALE));bp.set_attribute('mass','0')
 # Marked crossing uses actual mesh stripes; sidewalk-derived crossing uses raised walkway edges.
 for i in range(80):
  if definition=='marked':x=-8.25+(i%4)*.35;y=-6.8+(i//4)*.7;z=.002
  else:x=-8.25+(i%4)*.35;y=(-9.8+(i//4)*.3 if i<40 else 7.1+((i-40)//4)*.3);z=.15
  actor=world.spawn_actor(bp,carla.Transform(carla.Location(x=x-CENTER[0],y=y,z=z)));actor.set_simulate_physics(False);actor.set_collisions(False);actors.append(actor)
 return actors

def observe(actors):
 return [{'actor_id':a.id,'asset':a.attributes.get('mesh_path'),'position_m':[a.get_location().x,a.get_location().y,a.get_location().z],'body_vertices_m':[[p.x,p.y,p.z] for p in a.bounding_box.get_world_vertices(a.get_transform())]} for a in actors]
