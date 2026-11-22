"""CPU checks of the Native route and pre-capture source boundary."""
import importlib.util
import copy
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('c10808_native_capture', ROOT/'native_capture.py')
native_capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native_capture)
from runner import load_scene, path_points


class Point:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Carla:
    Location = Point
    Rotation = Point

    class Transform:
        def __init__(self, location, rotation):
            self.location = location
            self.rotation = rotation


class Map:
    name = 'fixture-map'

    def get_spawn_points(self):
        return [Carla.Transform(Carla.Location(x=100., y=50., z=0.), Carla.Rotation(yaw=90.))]

    def get_waypoint(self, location):
        if location.y < 30.:
            return None
        return types.SimpleNamespace(road_id=7, lane_type='Driving',
                                     lane_width=3.5,
                                     transform=types.SimpleNamespace(location=location))


class NativeCaptureTests(unittest.TestCase):
    def test_native_pedestrian_context_records_map_and_nearby_devices(self):
        location=types.SimpleNamespace(x=1.,y=2.,z=0.)
        operator=types.SimpleNamespace(id=7,type_id='walker.pedestrian.fixture',get_transform=lambda:
            types.SimpleNamespace(location=location))
        sign=types.SimpleNamespace(id=9,type_id='static.prop.sign.no_uturn',
            get_transform=lambda:types.SimpleNamespace(location=
                types.SimpleNamespace(x=3.,y=2.,z=0.)))
        far=types.SimpleNamespace(id=10,type_id='traffic.traffic_light',
            get_transform=lambda:types.SimpleNamespace(location=
                types.SimpleNamespace(x=100.,y=100.,z=0.)))
        world=types.SimpleNamespace(get_actors=lambda:[operator,sign,far])
        native_map=types.SimpleNamespace(
            get_waypoint=lambda point:types.SimpleNamespace(road_id=5,lane_id=-1,
                lane_type='Driving',junction_id=None),
            get_crosswalks=lambda:[types.SimpleNamespace(x=2.,y=2.,z=0.)])
        result=native_capture.pedestrian_context(world,native_map,operator,41,.05)
        self.assertEqual((result['frame'],result['operator_id']),(41,7))
        self.assertEqual(result['nearest_road_projection']['road_id'],5)
        self.assertEqual([d['actor_id'] for d in result['nearby_control_devices']],[9])
        self.assertEqual(len(result['nearby_crosswalk_vertices_m']),1)
        self.assertEqual(result['pedestrian_regulation_assessment'],'unresolved')

    def test_graph_capture_failure_releases_resources_and_restores_world(self):
        events=[]
        class World:
            def __init__(self):
                self.settings=types.SimpleNamespace(synchronous_mode=False,
                    fixed_delta_seconds=None)
                self.weather=object();self.frame=40
            def get_map(self):return object()
            def get_settings(self):return copy.deepcopy(self.settings)
            def apply_settings(self,value):
                self.settings=copy.deepcopy(value);events.append('apply_settings')
            def get_weather(self):return self.weather
            def set_weather(self,value):self.weather=value;events.append('set_weather')
            def get_snapshot(self):return types.SimpleNamespace(
                frame=self.frame,timestamp=types.SimpleNamespace(elapsed_seconds=0.))
            def tick(self):self.frame+=1;return self.frame
        world=World()
        class Client:
            def __init__(self,*args):pass
            def set_timeout(self,value):pass
            def get_world(self):return world
        class Actor:
            def __init__(self,name,index):
                self.id=index;self.type_id=name;self.name=name
            def set_transform(self,value):pass
            def destroy(self):events.append('destroy_'+self.name)
        actors={name:Actor(name,index) for index,name in
                enumerate(('sign','bicycle','operator'),1)}
        class Cameras:
            def __init__(self,*args):pass
            def close(self):events.append('cameras_closed')
        class FrameMap:
            def __init__(self,*args):pass
            def close(self):events.append('frame_map_closed')
        class PipelineCapture:
            def __init__(self,*args):pass
            def capture(self,*args,**kwargs):raise RuntimeError('graph collector failed')
            def close(self,confirmed=True):events.append('pipeline_closed_'+str(confirmed))
        def module(name,**attrs):
            value=types.ModuleType(name);value.__dict__.update(attrs);return value
        fake_modules={
            'carla':module('carla',Client=Client),
            'pipeline_capture':module('pipeline_capture',PipelineCapture=PipelineCapture),
            'worker_exchange.native_output':module('worker_exchange.native_output',
                FrameMap=FrameMap,seal_capture=lambda *a,**k:events.append('sealed')),
            'worker_exchange.world_restore':module('worker_exchange.world_restore',
                fields=lambda value:{'synchronous_mode':value.synchronous_mode,
                                     'fixed_delta_seconds':value.fixed_delta_seconds},
                equal=lambda left,right:left==right)}
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory);(output/'construction.json').write_text('{}')
            (output/'runner.py').write_text('')
            authorization=output/'authorization.txt';authorization.write_text('fixture')
            with patch.dict(sys.modules,fake_modules),patch.object(
                    native_capture,'discover_origin',return_value=(object(),{})),patch.object(
                    native_capture,'spawn_scene',return_value=actors),patch.object(
                    native_capture,'Cameras',Cameras),patch.object(
                    native_capture,'trajectory',return_value={
                        'operator':(0,0,0),'bicycle':(0,0,0),'phase':'mounted_approach'}),patch.object(
                    native_capture,'local_transform',return_value=object()):
                scene=load_scene();scene['duration_s']=.05
                with self.assertRaisesRegex(RuntimeError,'graph collector failed'):
                    native_capture.run_native(scene,output,'127.0.0.1',2000,
                                              authorization)
            self.assertIn('pipeline_closed_False',events)
            self.assertIn('frame_map_closed',events)
            self.assertIn('cameras_closed',events)
            self.assertIn('destroy_operator',events)
            self.assertFalse(world.settings.synchronous_mode)
            self.assertNotIn('sealed',events)
            self.assertTrue((output/'native-run-status.json').is_file())

    def test_walker_capture_proxy_exposes_neutral_control(self):
        actor=types.SimpleNamespace(id=12,type_id='walker.pedestrian.fixture',
                                    get_velocity=lambda: types.SimpleNamespace(
                                        x=0.,y=0.,z=0.))
        proxy=native_capture.WalkerCaptureProxy(actor)
        control=proxy.get_control()
        self.assertEqual(proxy.id,12)
        self.assertEqual(proxy.type_id,'walker.pedestrian.fixture')
        self.assertEqual((control.throttle,control.steer,control.brake),
                         (0.,0.,1.))
        self.assertTrue(control.hand_brake)
        self.assertFalse(control.reverse)

    def test_rotated_route_stays_on_one_driving_road(self):
        scene = load_scene()
        origin, context = native_capture.discover_origin(Map(), scene, Carla)
        pose = native_capture.local_transform(Carla, origin, 2., 3.)
        self.assertAlmostEqual(pose.location.x, 97.)
        self.assertAlmostEqual(pose.location.y, 52.)
        self.assertEqual(context['road_id'], 7)
        self.assertGreater(context['waypoint_count'],
                           sum(map(len, path_points(scene).values())))
        self.assertEqual(context['maximum_map_support_spacing_m'], 1.0)
        self.assertEqual(context['alley_classification'], 'unresolved_requires_local_review')

    def test_missing_road_support_rejected(self):
        scene = load_scene()
        class BadMap(Map):
            def get_waypoint(self, location):
                return None
        with self.assertRaisesRegex(ValueError, 'lacks connected turn geometry'):
            native_capture.discover_origin(BadMap(), scene, Carla)

    def test_snapped_distant_road_rejected(self):
        class DistantMap(Map):
            def get_waypoint(self, location):
                waypoint = super().get_waypoint(location)
                if waypoint is not None:
                    waypoint.transform.location = Carla.Location(
                        x=location.x+10., y=location.y, z=location.z)
                return waypoint
        with self.assertRaisesRegex(ValueError, 'lacks connected turn geometry'):
            native_capture.discover_origin(DistantMap(), load_scene(), Carla)

    def test_capture_requires_sealable_source_and_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authorization = root/'authorization.txt'
            authorization.write_text('fixture authorization source; no actual authorization claim')
            with self.assertRaisesRegex(ValueError, 'construction.json'):
                native_capture.run_native(load_scene(), root, '127.0.0.1', 2000,
                                          authorization)
            (root/'construction.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'runner.py'):
                native_capture.run_native(load_scene(), root, '127.0.0.1', 2000,
                                          authorization)

    def test_camera_frame_join_and_cleanup(self):
        class Sensor:
            def __init__(self):
                self.callback = None
                self.stopped = self.destroyed = False
            def listen(self, callback):
                self.callback = callback
            def stop(self):
                self.stopped = True
            def destroy(self):
                self.destroyed = True
        class World:
            def __init__(self):
                self.sensors = []
            def get_blueprint_library(self):
                return types.SimpleNamespace(find=lambda name: types.SimpleNamespace(
                    set_attribute=lambda key, value: None))
            def spawn_actor(self, blueprint, transform, attach_to):
                sensor = Sensor()
                self.sensors.append(sensor)
                return sensor
        class Pipe:
            def __init__(self):
                self.closed = False
                self.data = bytearray()
            def write(self, payload):
                self.data.extend(payload)
            def close(self):
                self.closed = True
        class Encoder:
            def __init__(self):
                self.stdin = Pipe()
            def wait(self, timeout):
                return 0
        world = World()
        encoders = []
        def spawn_encoder(*args, **kwargs):
            encoder = Encoder()
            encoders.append(encoder)
            return encoder
        with tempfile.TemporaryDirectory() as directory, patch.object(
                native_capture.subprocess, 'Popen', side_effect=spawn_encoder):
            cameras = native_capture.Cameras(world, object(), Path(directory), Carla)
            self.assertEqual(len(world.sensors), 4)
            for sensor in world.sensors:
                sensor.callback(types.SimpleNamespace(frame=41, raw_data=b'frame'))
            cameras.append(41)
            self.assertTrue(all(e.stdin.data == b'frame' for e in encoders))
            for sensor in world.sensors:
                sensor.callback(types.SimpleNamespace(frame=42, raw_data=b'frame'))
            with self.assertRaisesRegex(ValueError, 'camera/frame mismatch'):
                cameras.append(43)
            cameras.close()
            self.assertTrue(all(s.stopped and s.destroyed for s in world.sensors))
            self.assertTrue(all(e.stdin.closed for e in encoders))

    def test_partial_camera_spawn_closes_prior_sensor(self):
        class Sensor:
            stopped = destroyed = False
            def listen(self, callback):
                pass
            def stop(self):
                self.stopped = True
            def destroy(self):
                self.destroyed = True
        sensor = Sensor()
        class World:
            calls = 0
            def get_blueprint_library(self):
                return types.SimpleNamespace(find=lambda name: types.SimpleNamespace(
                    set_attribute=lambda key, value: None))
            def spawn_actor(self, blueprint, transform, attach_to):
                self.calls += 1
                return sensor if self.calls == 1 else None
        class Encoder:
            stdin = types.SimpleNamespace(closed=False, close=lambda: None)
            def wait(self, timeout):
                return 0
        with tempfile.TemporaryDirectory() as directory, patch.object(
                native_capture.subprocess, 'Popen', return_value=Encoder()):
            with self.assertRaisesRegex(ValueError, 'camera spawn failed'):
                native_capture.Cameras(World(), object(), Path(directory), Carla)
        self.assertTrue(sensor.stopped and sensor.destroyed)


if __name__ == '__main__':
    unittest.main()
