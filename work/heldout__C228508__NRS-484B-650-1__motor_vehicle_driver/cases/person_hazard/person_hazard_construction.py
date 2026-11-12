"""Native person crossing request and original geometry, without legal hazard judgment."""
from math import cos,hypot,pi,sin

def crossing_setup(route,distance,station_m,lateral_m):
    index=min(range(len(distance)),key=lambda i:abs(distance[i]-station_m))
    waypoint=route[index]
    center=waypoint.transform.location
    angle=waypoint.transform.rotation.yaw*pi/180
    right=(sin(angle),-cos(angle))
    spawn=(center.x+lateral_m*right[0],center.y+lateral_m*right[1],center.z+1.0)
    direction=(-right[0],-right[1])
    return spawn,direction,index

def spawn_walker(world,carla,route,distance,station_m=200,lateral_m=4.5,blueprint_index=0):
    blueprints=sorted(world.get_blueprint_library().filter('walker.pedestrian.*'),key=lambda b:b.id)
    if len(blueprints)<=blueprint_index:raise ValueError('Requested person blueprint unavailable')
    spawn,direction,index=crossing_setup(route,distance,station_m,lateral_m)
    transform=carla.Transform(carla.Location(x=spawn[0],y=spawn[1],z=spawn[2]),
                              route[index].transform.rotation)
    walker=world.try_spawn_actor(blueprints[blueprint_index],transform)
    if walker is None:raise ValueError('Native person spawn failed')
    return walker,direction

def control_walker(walker,carla,direction,speed_mps):
    walker.apply_control(carla.WalkerControl(direction=carla.Vector3D(direction[0],direction[1],0),
                                           speed=speed_mps,jump=False))

def person_sample(frame,time_s,ego,walker,ego_station):
    a,b=ego.get_location(),walker.get_location()
    distance=hypot(float(a.x-b.x),float(a.y-b.y))
    return {'frame':frame,'time_s':time_s,'ego_station_m':ego_station,
            'ego_xy_m':[float(a.x),float(a.y)],'person_xy_m':[float(b.x),float(b.y)],
            'person_actor_id':int(walker.id),'center_distance_m':distance,
            'person_blueprint_id':walker.type_id,
            'immediate_hazard_legal_judgment':None}
