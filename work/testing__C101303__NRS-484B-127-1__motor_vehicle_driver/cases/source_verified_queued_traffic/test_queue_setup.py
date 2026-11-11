import unittest
from types import SimpleNamespace as NS
from queue_setup import spawn_queued_vehicle

class Actor:
    def __init__(self,x):self.x=x;self.destroyed=False;self.control=None
    def get_location(self):return NS(x=self.x,y=0,z=0)
    def apply_control(self,control):self.control=control
    def destroy(self):self.destroyed=True
class World:
    def __init__(self,queued):self.queued=queued;self.calls=0
    def try_spawn_actor(self,blueprint,transform):self.calls+=1;return self.queued
class Tests(unittest.TestCase):
    def test_stationary_queue_is_spawned_braked_and_cleaned(self):
        queued=Actor(30);world=World(queued)
        with spawn_queued_vehicle(world,object(),object(),Actor(0),Actor(12),NS) as actor:
            self.assertIs(actor,queued);self.assertEqual(actor.control.brake,1.0)
        self.assertEqual(world.calls,1);self.assertTrue(queued.destroyed)
    def test_unsafe_position_is_rejected_and_cleaned(self):
        queued=Actor(14)
        with self.assertRaisesRegex(ValueError,'safely ahead'):
            with spawn_queued_vehicle(World(queued),object(),object(),Actor(0),Actor(12),NS):pass
        self.assertTrue(queued.destroyed)
