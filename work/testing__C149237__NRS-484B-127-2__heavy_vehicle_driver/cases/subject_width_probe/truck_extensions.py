def spawn_extras(carla,world,cfg,ego,lead,owned):
 trailers={}
 for role,tractor in [('ego',ego),('lead',lead)]:
  if cfg[role+'_class']=='combination':
   pose=tractor.get_transform();pose.location=pose.transform(carla.Location(x=-8))
   tr=world.spawn_actor(world.get_blueprint_library().find('vehicle.carlamotors.carlacola'),pose);owned.append(tr);trailers[role]=tr;tr.apply_control(carla.VehicleControl(throttle=0,brake=0,hand_brake=False))
 wp=world.get_map().get_waypoint_xodr(1,-1,390);pose=wp.transform;pose.location.y=-8
 entrant=world.spawn_actor(world.get_blueprint_library().find('vehicle.lincoln.mkz_2020'),pose);owned.append(entrant)
 return trailers,entrant

def apply_hitches(carla,ego,lead,trailers):
 for role,trailer in trailers.items():
  tractor=ego if role=='ego' else lead;hitch=tractor.get_transform().transform(carla.Location(x=-3.5));coupler=trailer.get_transform().transform(carla.Location(x=3.5));tv=tractor.get_velocity();rv=trailer.get_velocity()
  force=carla.Vector3D(x=1800*(hitch.x-coupler.x)+650*(tv.x-rv.x),y=1800*(hitch.y-coupler.y)+650*(tv.y-rv.y),z=0)
  trailer.add_force(force,coupler);tractor.add_force(carla.Vector3D(x=-force.x,y=-force.y,z=0),hitch)

def extend_state(value,trailer):
 if trailer:
  t=trailer.get_transform();value['drawn_body_vertices_m']=[[p.x,p.y,p.z] for p in trailer.bounding_box.get_world_vertices(t)];value['body_vertices_m']+=value['drawn_body_vertices_m']
 return value
