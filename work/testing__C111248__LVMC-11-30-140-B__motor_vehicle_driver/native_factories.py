"""CARLA factories for a reviewed, operator-owned blind-person encounter.

The source packet names already spawned participant and cue actor IDs. Those
actors are adopted for this attempt and destroyed on closure. The cue must be
actually attached to the reviewed person in the live world. This module does
not infer blindness or legal compliance from simulator appearance.
"""
from __future__ import annotations

import math

from carla_adapter import CarlaAdapter


class ConstructionAdapter:
    def __init__(self, world, plan):
        self.world = world
        self.plan = plan
        self.driver = None
        self.person = None
        self.cue = None

    def map_waypoint(self, map_id, road_id, lane_id, x, y):
        import carla
        if self.world.get_map().name != map_id:
            return None
        waypoint = self.world.get_map().get_waypoint(
            carla.Location(x=float(x), y=float(y), z=0.2),
            project_to_road=False)
        if waypoint is None or waypoint.road_id != road_id or waypoint.lane_id != lane_id:
            return None
        if math.hypot(waypoint.transform.location.x - x,
                      waypoint.transform.location.y - y) > 1.0:
            return None
        return waypoint

    def _adopt(self, actor_id, prefix):
        actor = self.world.get_actor(actor_id)
        if actor is None or not actor.is_alive or not actor.type_id.startswith(prefix):
            raise ValueError('reviewed Native actor unavailable: ' + prefix)
        return actor

    def spawn_vehicle(self, waypoint):
        self.driver = self._adopt(self.plan['driver_actor_id'], 'vehicle.')
        location = self.driver.get_location()
        if math.hypot(location.x - waypoint['x'], location.y - waypoint['y']) > 3.0:
            raise ValueError('reviewed driver spawn differs from route')
        return self.driver

    def spawn_pedestrian(self, pose):
        self.person = self._adopt(self.plan['pedestrian_actor_id'], 'walker.pedestrian.')
        location = self.person.get_location()
        if math.hypot(location.x - pose['x'], location.y - pose['y']) > 2.0:
            raise ValueError('reviewed protected-person pose differs')
        return self.person

    def attach_cue(self, person, cue):
        source = self.plan['cue_source']
        cue_id = source.get('cue_actor_id')
        if type(cue_id) is not int:
            raise ValueError('reviewed carried cue actor ID required')
        self.cue = self._adopt(cue_id, 'static.prop.')
        parent = getattr(self.cue, 'parent', None)
        if parent is None or parent.id != person.id:
            raise ValueError('carried cue is not attached to protected person')
        if source.get('cue') != cue:
            raise ValueError('live cue differs from reviewed source')
        return self.cue

    def actor_readback(self, actor):
        result = {'alive': bool(actor.is_alive), 'actor_id': actor.id,
                  'type_id': actor.type_id}
        if actor is self.cue:
            result['cue'] = self.plan['cue_source']['cue']
            result['attached_to'] = getattr(getattr(actor, 'parent', None), 'id', None)
        return result

    def destroy_actor(self, actor):
        if actor is not None and actor.is_alive:
            actor.destroy()


class CaptureAdapter(CarlaAdapter):
    def __init__(self, world, driver, person, sensors, collision_sensor,
                 context_reader, control_factory, pipeline):
        self.collision_sensor = collision_sensor
        self.pipeline = pipeline
        super().__init__(world, driver, person, sensors, context_reader,
                         control_factory, destroy_sensors=True)

    def observe(self, frame):
        result = super().observe(frame)
        self.pipeline.capture(frame, self.last_time)
        return result

    def close(self):
        if self.closed:
            return
        try:
            super().close()
        finally:
            try:
                self.pipeline.close()
            finally:
                self.collision_sensor.stop()
                self.collision_sensor.destroy()


def construction_adapter_factory(world, plan):
    return ConstructionAdapter(world, plan)


def capture_adapter_factory(world, plan, constructed, *, client, output, case_id):
    import carla
    from pipeline_capture import PipelineCapture
    driver = world.get_actor(plan['driver_actor_id'])
    person = world.get_actor(plan['pedestrian_actor_id'])
    if driver is None or person is None:
        raise ValueError('reviewed participant absent at capture')
    route = plan['route_waypoints']
    dx = route[-1]['x'] - route[0]['x']
    dy = route[-1]['y'] - route[0]['y']
    length = math.hypot(dx, dy)
    if length <= 1.0:
        raise ValueError('reviewed route direction unavailable')
    ux, uy = dx / length, dy / length
    person_start = person.get_location()
    poses = {
        'front': (carla.Transform(carla.Location(
            x=(route[0]['x'] + route[-1]['x']) / 2,
            y=(route[0]['y'] + route[-1]['y']) / 2, z=20.0),
            carla.Rotation(pitch=-90.0)), None, 1920, 1080),
        'left': (carla.Transform(carla.Location(x=person_start.x - 5 * ux,
            y=person_start.y - 5 * uy, z=2.5), carla.Rotation(yaw=math.degrees(math.atan2(uy, ux)))),
            None, 1280, 720),
        'right': (carla.Transform(carla.Location(x=person_start.x + 4 * uy,
            y=person_start.y - 4 * ux, z=2.5),
            carla.Rotation(yaw=math.degrees(math.atan2(-ux, -uy)))), None, 1280, 720),
        'rear': (carla.Transform(carla.Location(x=0.2, z=1.7), carla.Rotation()),
            driver, 1280, 720),
    }
    sensors = {}
    collision = None
    pipeline = None
    try:
        for name, (pose, parent, width, height) in poses.items():
            blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
            blueprint.set_attribute('image_size_x', str(width))
            blueprint.set_attribute('image_size_y', str(height))
            blueprint.set_attribute('sensor_tick', '0.05')
            sensor = world.spawn_actor(blueprint, pose, attach_to=parent) if parent else world.spawn_actor(blueprint, pose)
            if sensor is None:
                raise ValueError('original camera spawn failed: ' + name)
            sensors[name] = sensor
        collision_bp = world.get_blueprint_library().find('sensor.other.collision')
        collision = world.spawn_actor(collision_bp, carla.Transform(), attach_to=driver)
        if collision is None:
            raise ValueError('original collision sensor spawn failed')
        contacts = set()
        collision.listen(lambda event: contacts.add(event.frame) if event.other_actor.id == person.id else None)

        def context_reader(frame):
            location = person.get_location()
            vehicle = driver.get_location()
            lateral = abs((location.x - route[0]['x']) * uy -
                          (location.y - route[0]['y']) * ux)
            forward = (location.x - vehicle.x) * ux + (location.y - vehicle.y) * uy
            in_path = lateral <= 2.0 and forward >= -2.0
            clear = lateral >= 3.0 or forward < -3.0
            if not clear and hasattr(person, 'apply_control'):
                person.apply_control(carla.WalkerControl(direction=carla.Vector3D(-uy, ux, 0.0), speed=0.6))
            speed = driver.get_velocity().length()
            return {'frame': frame, 'person_actor_id': person.id,
                    'driver_actor_id': driver.id, 'person_in_path': in_path,
                    'person_clear': clear, 'contact': frame in contacts,
                    'precaution': speed <= 0.05 and in_path}

        pipeline = PipelineCapture(client, driver, output, case_id)
        return CaptureAdapter(world, driver, person, sensors, collision,
                              context_reader, carla.VehicleControl, pipeline)
    except BaseException:
        if pipeline is not None:
            pipeline.close(confirmed=False)
        for sensor in sensors.values():
            sensor.destroy()
        if collision is not None:
            collision.destroy()
        raise
