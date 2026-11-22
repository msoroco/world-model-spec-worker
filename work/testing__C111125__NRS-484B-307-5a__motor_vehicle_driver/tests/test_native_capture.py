import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('native_capture',ROOT/'native_capture.py')
native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)


class Point:
    def __init__(self,x,y,z=0):self.x=x;self.y=y;self.z=z


class Light:
    type_id='traffic.traffic_light';
    def __init__(self,ident,state='Green'):
        self.id=ident;self.state=state
    def get_state(self):return self.state
    def get_transform(self):
        return type('T',(),{'location':Point(0,0,4),'rotation':type('R',(),{'yaw':90})()})()


class Waypoint:
    road_id=1;lane_id=-1
    def __init__(self,x):self.transform=type('T',(),{'location':Point(x,0)})()


class Map:
    def __init__(self,missing=False):self.missing=missing
    def get_waypoint(self,point):return None if self.missing else Waypoint(point.x)


class Carla:
    Location=Point


class NativeSourceTests(unittest.TestCase):
    def test_participant_inventory_includes_external_actors_and_excludes_ego(self):
        class Box:
            def get_world_vertices(self,_):return [Point(0,0),Point(1,0),Point(1,1),Point(0,1)]
        class Actor:
            bounding_box=Box()
            def __init__(self,ident):self.id=ident
            def get_transform(self):return object()
        class Group:
            def filter(self,pattern):
                return [Actor(1),Actor(2),Actor(3)] if pattern=='vehicle.*' else [Actor(4)]
        class World:
            def get_actors(self):return Group()
        rows=native.participant_inventory(World(),Actor(1))
        self.assertEqual([row['id'] for row in rows],[2,3,4])
        self.assertEqual(rows[-1]['role'],'pedestrian')
        self.assertTrue(all(row['lawfully_present'] is None for row in rows))

    def reviewed_source(self,folder,actor_id=7):
        folder=Path(folder);asset=folder/'original-head.mesh'
        asset.write_bytes(b'CPU fixture representing original head mesh')
        packet={'format':'c111125-reviewed-arrow-asset-v1',
                'review_method':'complete-original-head-indication-inventory',
                'reviewer':'CPU fixture reviewer',
                'installation_source_ref':'CPU fixture installation',
                'asset_file':asset.name,
                'asset_sha256':hashlib.sha256(asset.read_bytes()).hexdigest(),
                'asset_type':'original_mesh','actor_id':actor_id,
                'blueprint_id':'traffic.traffic_light','faces_ego_approach':True,
                'green_indications':[{'color':'green','shape':'arrow','direction':'straight'}],
                'other_illuminated_on_green':[],
                'position_m':[0,0,4],'yaw_deg':90}
        (folder/'review.json').write_text(json.dumps(packet))
        return packet

    def test_reviewed_head_binds_exact_live_actor_and_frame(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            self.reviewed_source(source)
            bindings,names=native.retain_reviewed_sources(source,output)
            self.assertEqual(len(names),2)
            row=native.signal_snapshot([Light(7)],18,bindings)
            self.assertTrue(row['aspect']['source_verified'])
            self.assertEqual(row['facing_head_id'],7)
            self.assertEqual(row['aspect']['observed_frame'],18)
            self.assertEqual(row['aspect']['illuminated_indications'],
                             [{'color':'green','shape':'arrow','direction':'straight'}])
            red=native.signal_snapshot([Light(7,'Red')],19,bindings)
            self.assertFalse(red['aspect']['source_verified'])
            self.assertEqual(red['aspect']['illuminated_indications'],[])
            with self.assertRaisesRegex(ValueError,'actor absent'):
                native.signal_snapshot([Light(8)],18,bindings)
            with self.assertRaisesRegex(ValueError,'slot'):
                native.signal_snapshot([Light(7)],18,bindings,slot=1)
            class ShiftedLight(Light):
                def get_transform(self):
                    return type('T',(),{'location':Point(2,0,4),
                                       'rotation':type('R',(),{'yaw':90})()})()
            with self.assertRaisesRegex(ValueError,'position mismatch'):
                native.signal_snapshot([ShiftedLight(7)],18,bindings)

    def test_review_packet_rejects_broken_or_ambiguous_source(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            packet=self.reviewed_source(source)
            path=Path(source)/'review.json'
            packet['other_illuminated_on_green']=[{'color':'green','shape':'circle'}]
            path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError,'other indications'):
                native.retain_reviewed_sources(source,output)
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            packet=self.reviewed_source(source)
            path=Path(source)/'review.json'
            packet['asset_sha256']='0'*64
            path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError,'hash mismatch'):
                native.retain_reviewed_sources(source,output)

    def test_camera_close_destroys_sensors_after_encoder_failure(self):
        class Sensor:
            stopped=False;destroyed=False
            def stop(self):self.stopped=True
            def destroy(self):self.destroyed=True
        class Pipe:
            closed=False
            def close(self):self.closed=True
        class Encoder:
            stdin=Pipe()
            def wait(self,timeout):return 1
        sensor=Sensor();bank=native.CameraBank.__new__(native.CameraBank)
        bank.sensors=[sensor];bank.encoders={'overview':Encoder()}
        with self.assertRaisesRegex(RuntimeError,'encoder failed'):
            bank.close()
        self.assertTrue(sensor.stopped)
        self.assertTrue(sensor.destroyed)
    def test_generic_green_is_never_promoted_to_arrow(self):
        row=native.signal_snapshot([Light(8),Light(7)],18)
        self.assertEqual([item['actor_id'] for item in row['candidate_lights']],[7,8])
        self.assertFalse(row['aspect']['source_verified'])
        self.assertEqual(row['aspect']['illuminated_indications'],[])
        self.assertIsNone(row['facing_head_id'])
        with self.assertRaisesRegex(ValueError,'duplicate'):
            native.signal_snapshot([Light(7),Light(7)],18)

    def test_map_route_requires_original_waypoints(self):
        sys.path.insert(0,str(ROOT))
        try:
            from runner import load_scene
            scene=load_scene()
            context=native.map_context(Map(),scene,Carla)
            self.assertFalse(context['lawful_presence_source_verified'])
            with self.assertRaisesRegex(ValueError,'matching Native driving waypoint'):
                native.map_context(Map(missing=True),scene,Carla)
        finally:sys.path.remove(str(ROOT))

    def test_failed_map_preflight_restores_world_without_seal(self):
        class Settings:
            synchronous_mode=False;fixed_delta_seconds=None
        class World:
            def __init__(self):self.settings=Settings();self.applied=[]
            def get_settings(self):return self.settings
            def get_map(self):return Map(missing=True)
            def apply_settings(self,value):self.applied.append(value)
        world=World()
        class Client:
            def __init__(self,*_):pass
            def set_timeout(self,_):pass
            def get_world(self):return world
        fake_carla=types.SimpleNamespace(Client=Client,Location=Point)
        output=types.SimpleNamespace(FrameMap=object,physical_result=lambda _,value:value,
                                     write_result=lambda *_:None,
                                     seal_capture=lambda *_ , **__:self.fail('failed capture was sealed'))
        restore=types.SimpleNamespace(fields=lambda obj:{'synchronous_mode':obj.synchronous_mode,
                                                          'fixed_delta_seconds':obj.fixed_delta_seconds},
                                      equal=lambda a,b:a==b)
        modules={'carla':fake_carla,'pipeline_capture':types.SimpleNamespace(PipelineCapture=object),
                 'worker_exchange':types.ModuleType('worker_exchange'),
                 'worker_exchange.native_output':output,
                 'worker_exchange.world_restore':restore}
        sys.path.insert(0,str(ROOT))
        try:
            from runner import load_scene
            with tempfile.TemporaryDirectory() as folder, patch.dict(sys.modules,modules):
                with self.assertRaisesRegex(ValueError,'matching Native driving waypoint'):
                    native.run_native(load_scene(),folder,'127.0.0.1',2000)
                self.assertTrue((Path(folder)/'native-run-status.json').is_file())
                self.assertFalse((Path(folder)/'capture-seal.json').exists())
                self.assertEqual(len(world.applied),1)
        finally:sys.path.remove(str(ROOT))


if __name__=='__main__':unittest.main()
