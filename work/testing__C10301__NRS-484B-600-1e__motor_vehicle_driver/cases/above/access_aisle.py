"""Physical accepted road-line mesh adaptation for the adjacent access aisle."""
ASSET='/Game/Carla/Static/RoadLine/SM_BassicTrafficLineCube_trafficlineCube.SM_BassicTrafficLineCube_trafficlineCube'
EXTENT=(.06204589828848839,.06204365938901901,.0038028834387660027)
CENTER=(.061835937201976776,0,2.38418573772492e-09)
SCALE=.35/(2*EXTENT[1])
def positions():
 points=[]
 for i in range(58):
  x=400+.35*i
  points += [(x,5.175),(x,7.325)]
 for i in range(8):points += [(400,5+.35*i),(420,5+.35*i)]
 for stripe in range(8):
  for i in range(6):points.append((400+stripe*2.5+i*.35,5.2+i*.35))
 return points
def spawn(carla,world):
 bp=world.get_blueprint_library().find('static.prop.mesh');bp.set_attribute('mesh_path',ASSET);bp.set_attribute('scale',str(SCALE));bp.set_attribute('mass','0');actors=[]
 for i,(x,y) in enumerate(positions()):
  bp.set_attribute('role_name','access_aisle_mark_%03d'%i);a=world.spawn_actor(bp,carla.Transform(carla.Location(x=x-CENTER[0]*SCALE,y=y,z=.002-EXTENT[2]*SCALE)));a.set_simulate_physics(False);a.set_collisions(False);actors.append(a)
 return actors
