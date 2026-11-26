"""Expose a real Walker to the pinned vehicle-oriented capture interface.

The proxy delegates every physical measurement to the original actor. Vehicle
control and lighting fields are null because they do not apply to a Walker.
"""


class WalkerControlView:
    def __init__(self, control):
        self.direction = control.direction
        self.speed = control.speed
        self.jump = control.jump
        for name in ('throttle', 'steer', 'brake', 'hand_brake', 'reverse',
                     'manual_gear_shift', 'gear'):
            setattr(self, name, None)


class WalkerView:
    def __init__(self, actor):
        if not actor.type_id.startswith('walker.'):
            raise ValueError('Walker adapter requires an original Walker actor')
        self.actor = actor

    def __getattr__(self, name):
        return getattr(self.actor, name)

    def get_control(self):
        return WalkerControlView(self.actor.get_control())

    def is_at_traffic_light(self):
        return None


class WorldView:
    def __init__(self, world, walker):
        self.world = world
        self.walker = walker

    def __getattr__(self, name):
        return getattr(self.world, name)

    def get_actor(self, actor_id):
        actor = self.world.get_actor(actor_id)
        return self.walker if actor is not None and actor.id == self.walker.id else actor


class ClientView:
    def __init__(self, client, world):
        self.client = client
        self.world = world

    def __getattr__(self, name):
        return getattr(self.client, name)

    def get_world(self):
        return self.world


def adapt(client, walker):
    """Bind the same original actor ID in PipelineCapture and SGG lookups."""
    from carla_sgg import sgg
    if not getattr(sgg.copy_carla_vehicle_lights, '_walker_adapter', False):
        original = sgg.copy_carla_vehicle_lights

        def lights(attributes, actor):
            if actor.type_id.startswith('walker.'):
                attributes['vehicle_light_state'] = None
                attributes['vehicle_lights_applicable'] = False
                return None
            return original(attributes, actor)

        lights._walker_adapter = True
        sgg.copy_carla_vehicle_lights = lights
    view = WalkerView(walker)
    return ClientView(client, WorldView(client.get_world(), view)), view
