"""Native reverse request and readback for a source-reviewed approach."""
from contextlib import contextmanager
@contextmanager
def reverse_vehicle(world,vehicle,control_factory,*,throttle=0.2):
 if not 0<throttle<=0.4:raise ValueError('Conservative reverse throttle required')
 original=vehicle.get_control()
 try:
  vehicle.apply_control(control_factory(throttle=throttle,brake=0.0,reverse=True))
  world.tick()
  if vehicle.get_control().reverse is not True:raise ValueError('Native reverse readback failed')
  yield vehicle
 finally:
  vehicle.apply_control(original)
  world.tick()
  if vehicle.get_control().reverse!=original.reverse:raise ValueError('Vehicle control restoration failed')
