"""Spawn distinct motor vehicles for a source-reviewed caravan route."""
from contextlib import contextmanager

def _xy(actor):
 p=actor.get_location();return float(p.x),float(p.y)
@contextmanager
def spawn_caravan(world, vehicles, *, min_initial_separation_m=3.0):
 if len(vehicles)<3:raise ValueError('At least three caravan participants required')
 owned=[]
 try:
  for blueprint,transform in vehicles:
   actor=world.try_spawn_actor(blueprint,transform)
   if actor is None:raise ValueError('Native caravan vehicle spawn failed')
   owned.append(actor)
  positions=[_xy(actor) for actor in owned]
  for i,p in enumerate(positions):
   for q in positions[i+1:]:
    if ((p[0]-q[0])**2+(p[1]-q[1])**2)**.5<min_initial_separation_m:
     raise ValueError('Caravan initial positions overlap')
  yield owned
 finally:
  for actor in reversed(owned):actor.destroy()
