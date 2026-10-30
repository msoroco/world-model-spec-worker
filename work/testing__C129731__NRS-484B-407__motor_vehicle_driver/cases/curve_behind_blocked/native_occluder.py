def spawn(carla,world,map_,cfg):
 actors=[]
 for direction in cfg['occluded_directions']:
  station=cfg['turn_station_m']+(55 if direction=='ahead_opposing' else -55)
  wp=map_.get_waypoint_xodr(1,-1,station)
  options=list(world.get_blueprint_library().filter('static.prop.*container*'))
  if not options:raise ValueError('Native occluder blueprint unavailable: static.prop.*container*')
  bp=options[0];pose=wp.transform;pose.location.z+=2
  actor=world.spawn_actor(bp,pose);actor.set_simulate_physics(False);actors.append(actor)
 return actors
