"""CPU checks for reviewed live actor adoption and carried-cue identity."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_factories import ConstructionAdapter


class Location:
    def __init__(self, x, y):
        self.x, self.y = x, y


class Actor:
    def __init__(self, actor_id, type_id, x=0, y=0, parent=None):
        self.id, self.type_id = actor_id, type_id
        self.location = Location(x, y)
        self.parent = parent
        self.is_alive = True

    def get_location(self):
        return self.location

    def destroy(self):
        self.is_alive = False


class World:
    def __init__(self, actors):
        self.actors = {actor.id: actor for actor in actors}

    def get_actor(self, actor_id):
        return self.actors.get(actor_id)


class NativeFactoriesTest(unittest.TestCase):
    def setUp(self):
        self.driver = Actor(4, 'vehicle.fixture', 0, 0)
        self.person = Actor(5, 'walker.pedestrian.fixture', 10, 2)
        self.cue = Actor(6, 'static.prop.fixture', 10, 2, self.person)
        self.plan = {'driver_actor_id': 4, 'pedestrian_actor_id': 5,
                     'cue_source': {'cue_actor_id': 6, 'cue': 'white_cane'}}
        self.adapter = ConstructionAdapter(World((self.driver, self.person, self.cue)), self.plan)

    def test_adopts_reviewed_live_participants_and_attached_cue(self):
        driver = self.adapter.spawn_vehicle({'x': 0, 'y': 0})
        person = self.adapter.spawn_pedestrian({'x': 10, 'y': 2})
        cue = self.adapter.attach_cue(person, 'white_cane')
        self.assertEqual((driver.id, person.id, cue.id), (4, 5, 6))
        self.assertEqual(self.adapter.actor_readback(cue)['attached_to'], 5)
        self.adapter.destroy_actor(cue)
        self.assertFalse(cue.is_alive)

    def test_rejects_wrong_live_identity_and_detached_cue(self):
        self.adapter.world.actors.pop(4)
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            self.adapter.spawn_vehicle({'x': 0, 'y': 0})
        self.adapter.world.actors[4] = self.driver
        self.cue.parent = None
        with self.assertRaisesRegex(ValueError, 'not attached'):
            self.adapter.attach_cue(self.person, 'white_cane')


if __name__ == '__main__':
    unittest.main()
