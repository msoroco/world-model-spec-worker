import unittest
from types import SimpleNamespace as NS
from person_hazard_construction import crossing_setup
class PersonSiteTest(unittest.TestCase):
    def test_person_starts_off_lane_and_moves_across(self):
        waypoint=NS(transform=NS(location=NS(x=200,y=0,z=0),rotation=NS(yaw=0)))
        spawn,direction,index=crossing_setup([waypoint],[200],200,4.5)
        self.assertEqual(index,0)
        self.assertEqual(spawn,(200,-4.5,1.0))
        self.assertEqual(direction,(0.0,1.0))
