import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from native_pair import construct_pair, step_pair
from test_median_route_control import scene


class Actor:
    def __init__(self,x,y,yaw=0,speed=0):
        self.pose=NS(location=NS(x=x,y=y),rotation=NS(yaw=yaw))
        self.velocity=NS(x=speed,y=0,z=0)
        self.commands=[]
        self.destroyed=False
    def get_transform(self):return self.pose
    def get_velocity(self):return self.velocity
    def apply_control(self,command):self.commands.append(command)
    def destroy(self):self.destroyed=True


class Actors(list):
    def filter(self,pattern):return self


class World:
    def __init__(self,actors,fail_second=False):
        self.sign=NS(id=17,trigger_volume=NS(contains=lambda point,transform:True),
                     get_transform=lambda:None)
        self.actors=actors
        self.fail_second=fail_second
        self.calls=[]
    def get_actors(self):return Actors([self.sign])
    def try_spawn_actor(self,blueprint,transform):
        self.calls.append((blueprint,transform))
        if self.fail_second and len(self.calls)==2:return None
        return self.actors[len(self.calls)-1]


class NativePairTests(unittest.TestCase):
    def test_spawns_both_and_destroys_even_on_capture_error(self):
        ego,other=Actor(0,0),Actor(15,-15)
        world=World([ego,other])
        waypoint=NS(transform=NS(location='ego-approach'))
        with self.assertRaisesRegex(RuntimeError,'capture'):
            with construct_pair(world,scene(),'ego-blueprint','other-blueprint',
                                'ego-transform','other-transform',waypoint) as (a,b,sign):
                self.assertIs(a,ego);self.assertIs(b,other);self.assertEqual(sign.id,17)
                raise RuntimeError('capture failed')
        self.assertEqual(world.calls,[('ego-blueprint','ego-transform'),
                                      ('other-blueprint','other-transform')])
        self.assertTrue(ego.destroyed and other.destroyed)

    def test_failed_second_spawn_cleans_first(self):
        ego=Actor(0,0)
        world=World([ego],fail_second=True)
        waypoint=NS(transform=NS(location='ego-approach'))
        with self.assertRaisesRegex(ValueError,'other Native spawn failed'):
            with construct_pair(world,scene(),'ego','other','et','ot',waypoint):pass
        self.assertTrue(ego.destroyed)

    def test_wrong_sign_rejected_before_spawning(self):
        world=World([Actor(0,0),Actor(15,-15)])
        world.sign.id=99
        waypoint=NS(transform=NS(location='ego-approach'))
        with self.assertRaisesRegex(ValueError,'sign ID'):
            with construct_pair(world,scene(),'ego','other','et','ot',waypoint):pass
        self.assertEqual(world.calls,[])

    def test_stop_wait_and_release_apply_native_commands(self):
        ego,other=Actor(8,0,speed=.05),Actor(15,-15,speed=0)
        carla=NS(VehicleControl=lambda:NS())
        progress,stopped,commands=step_pair(carla,ego,other,scene(),
                                            {'ego':1,'other':1},False,False,False)
        self.assertTrue(stopped)
        self.assertEqual(commands['ego']['brake'],1)
        self.assertEqual(commands['other']['brake'],1)
        progress,stopped,commands=step_pair(carla,ego,other,scene(),
                                            progress,stopped,True,True)
        self.assertGreater(commands['ego']['throttle'],0)
        self.assertGreater(commands['other']['throttle'],0)
        self.assertEqual(len(ego.commands),2)
        self.assertEqual(len(other.commands),2)

if __name__=='__main__':unittest.main()
