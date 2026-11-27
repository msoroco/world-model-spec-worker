"""Native context actor requests, with source review required after capture."""
from road import SIGNAL_STATION_M


def _pose(carla,x,y):
    return carla.Transform(carla.Location(x=x,y=y,z=1.0),carla.Rotation(yaw=0))


def spawn_context(world,carla,library,activity,exception,target_center_x):
    """Return owned actors and their requested role, not asserted legal authority."""
    actors=[]
    requests=[]
    if exception=='traffic_conflict':
        blueprint=library.find('vehicle.tesla.model3')
        blueprint.set_attribute('role_name','traffic_conflict_probe')
        actor=world.try_spawn_actor(blueprint,_pose(carla,target_center_x+6,-1.85))
        if actor is None:raise RuntimeError('Traffic conflict probe did not spawn')
        actor.apply_control(carla.VehicleControl(hand_brake=True))
        actors.append(actor);requests.append('lead_vehicle_on_approach')
    if exception=='police_direction':
        blueprint=library.find('walker.pedestrian.0001')
        blueprint.set_attribute('role_name','police_direction_proxy_requires_review')
        actor=world.try_spawn_actor(blueprint,_pose(carla,SIGNAL_STATION_M-5,-5.5))
        if actor is None:raise RuntimeError('Police direction proxy did not spawn')
        actors.append(actor);requests.append('human_direction_proxy')
    if activity=='park':
        blueprint=library.find('walker.pedestrian.0001')
        blueprint.set_attribute('role_name','parked_driver_departure_proxy_requires_review')
        actor=world.try_spawn_actor(blueprint,_pose(carla,target_center_x-3,-5.5))
        if actor is None:raise RuntimeError('Parking driver proxy did not spawn')
        actors.append(actor);requests.append('driver_departure_proxy')
    return actors,requests
