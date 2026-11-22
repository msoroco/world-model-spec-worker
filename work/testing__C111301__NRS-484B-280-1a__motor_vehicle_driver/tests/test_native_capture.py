import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from native_capture import Cameras,select_chair,connected_route,pedestrian_station,spawn_entities
from runner import load_scene


class Blueprint:
    def __init__(self,name):self.id=name


class Library:
    def __init__(self,names):self.names=names
    def filter(self,pattern):
        import fnmatch
        return [Blueprint(name) for name in self.names if fnmatch.fnmatch(name,pattern)]


class NativeCaptureTests(unittest.TestCase):
    def test_camera_cleanup_destroys_every_sensor_after_encoder_failure(self):
        class Sensor:
            stopped=False;destroyed=False
            def stop(self):self.stopped=True
            def destroy(self):self.destroyed=True
        class Pipe:
            closed=False
            def close(self):self.closed=True
        class Encoder:
            def __init__(self,code):self.code=code;self.stdin=Pipe()
            def wait(self,timeout):return self.code
        sensors=[Sensor(),Sensor()]
        bank=Cameras.__new__(Cameras)
        bank.sensors=sensors
        bank.encoders={'overview':Encoder(1),'approach':Encoder(0)}
        with self.assertRaisesRegex(RuntimeError,'encoder failed'):
            bank.close()
        self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in sensors))
        self.assertTrue(all(process.stdin.closed for process in bank.encoders.values()))

    def test_wheelchair_asset_is_distinct_and_named(self):
        library=Library(['static.prop.wheelchair02','walker.pedestrian.0001'])
        self.assertEqual(select_chair(library,'static.prop.wheelchair*').id,
                         'static.prop.wheelchair02')
        with self.assertRaisesRegex(ValueError,'No distinct Native manual-wheelchair asset'):
            select_chair(Library(['static.prop.chair01']),'static.prop.*')

    def test_fallback_finds_renamed_asset(self):
        library=Library(['static.prop.park_wheelchair01'])
        with self.assertRaises(ValueError):select_chair(library,'static.prop.wheelchair*')
        self.assertEqual(select_chair(library,'static.prop.*wheelchair*').id,
                         'static.prop.park_wheelchair01')

    def test_native_ego_route_requires_forward_waypoint_chain(self):
        class Point:
            def __init__(self,x):self.x=x;self.y=0
        class Transform:
            def __init__(self,x):self.location=Point(x)
        class Waypoint:
            def __init__(self,x):
                self.transform=Transform(x);self.road_id=1;self.lane_id=1;self.following=[]
            def next(self,distance):return self.following
        points=[Waypoint(x) for x in (0,2,4,6)]
        for first,second in zip(points,points[1:]):first.following=[second]
        self.assertTrue(connected_route(points[0],points[-1]))
        points[1].following=[]
        self.assertFalse(connected_route(points[0],points[-1]))

    def test_pedestrian_motion_is_bounded_at_authored_speed(self):
        scene=load_scene()
        scene['wheelchair_path_setup']='crossing'
        self.assertAlmostEqual(pedestrian_station(scene,0),-5.94)
        self.assertAlmostEqual(pedestrian_station(scene,19),-4.8)
        self.assertEqual(pedestrian_station(scene,500),6)
        scene['wheelchair_path_setup']='clear_path'
        self.assertEqual(pedestrian_station(scene,500),5)

    def test_native_actor_creation_and_partial_cleanup(self):
        class Actor:
            def __init__(self,ident):self.id=ident;self.destroyed=False
            def destroy(self):self.destroyed=True
        class World:
            def __init__(self,fail_at=None):self.created=[];self.fail_at=fail_at
            def spawn_actor(self,blueprint,transform):
                if len(self.created)==self.fail_at:raise RuntimeError('spawn failed')
                actor=Actor(len(self.created)+1);self.created.append((blueprint,transform,actor))
                return actor
        scene=load_scene();scene['wheelchair_path_setup']='crossing'
        transform=lambda x,y,yaw=0:(x,y,yaw)
        world=World();actors=spawn_entities(world,scene,'ego','manual-chair','person',transform)
        self.assertEqual([item[0] for item in world.created],['ego','manual-chair','person'])
        self.assertEqual(world.created[1][1],(0,-6,90))
        self.assertEqual({actor.id for actor in actors},{1,2,3})
        broken=World(fail_at=2)
        with self.assertRaisesRegex(RuntimeError,'spawn failed'):
            spawn_entities(broken,scene,'ego','manual-chair','person',transform)
        self.assertTrue(all(item[2].destroyed for item in broken.created))


if __name__=='__main__':unittest.main()
