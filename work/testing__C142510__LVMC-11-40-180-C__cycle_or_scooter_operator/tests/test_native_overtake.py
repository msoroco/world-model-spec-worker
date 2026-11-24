"""CPU construction protocol tests; real sound and sidewalk require later review."""
import hashlib
import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('c142510_native',ROOT/'native_overtake.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class Adapter:
    def __init__(self):self.calls=[];self.destroyed=[];self.fail=None
    def map_opendrive_bytes(self):return b'<OpenDRIVE fixture/>'
    def sidewalk_route_readback(self,*args):self.calls.append('sidewalk_route');return self.fail!='route'
    def spawn_rider(self,*args,**kwargs):self.calls.append('rider');return object()
    def spawn_pedestrian(self,*args,**kwargs):self.calls.append('pedestrian');return object()
    def attach_audible_emitter(self,*args,**kwargs):self.calls.append('emitter');return object()
    def read_emitter(self,*args):return {'physically_present':self.fail!='emitter'}
    def attach_pedestrian_microphone(self,*args,**kwargs):self.calls.append('microphone');return object()
    def read_microphone(self,*args):return {'recording_enabled':self.fail!='microphone'}
    def set_rider_route(self,*args):self.calls.append('set_rider_route')
    def set_pedestrian_route(self,*args):self.calls.append('set_pedestrian_route')
    def emit_audible_signal(self,*args):self.calls.append('emit')
    def destroy(self,obj):self.destroyed.append(obj)


def site():
    return {'cell_id':'C142510','physical_surface_kind':'sidewalk',
        'sidewalk_connected':True,'map_sha256':hashlib.sha256(b'<OpenDRIVE fixture/>').hexdigest(),
        'sidewalk_source_citation':'fixture source','connected_route_citation':'fixture route',
        'rider_blueprint_sha256':'bicycle','pedestrian_blueprint_sha256':'person',
        'audible_emitter_source_sha256':'speaker','microphone_source_sha256':'mic',
        'rider_kind':'bicycle','sidewalk_id':'walk A',
        'rider_route_xyz_m':[[-4,0,0],[4,0,0]],
        'pedestrian_route_xyz_m':[[-1,0,0],[3,0,0]]}


class NativeTest(unittest.TestCase):
    def test_builds_two_participants_and_actual_audio_devices(self):
        a=Adapter();result=m.build(a,site())
        self.assertEqual(len(result['owned']),4)
        self.assertEqual(a.calls.count('sidewalk_route'),2)
        self.assertIn('set_rider_route',a.calls)
        self.assertFalse(m.request_signal(a,result['emitter'],101,102))
        self.assertTrue(m.request_signal(a,result['emitter'],102,102))
        self.assertEqual(a.calls.count('emit'),1)

    def test_wrong_surface_map_and_missing_microphone_rejected(self):
        a=Adapter();p=site();p['physical_surface_kind']='nonmotorized_trail'
        with self.assertRaisesRegex(ValueError,'connected physical sidewalk'):
            m.build(a,p)
        p=site();p['rider_kind']='motor_vehicle'
        with self.assertRaisesRegex(ValueError,'covered rider kind'):
            m.build(a,p)
        p=site();p['map_sha256']='wrong'
        with self.assertRaisesRegex(ValueError,'live map differs'):
            m.build(a,p)
        p=site();a=Adapter();a.fail='microphone'
        with self.assertRaisesRegex(ValueError,'microphone readback missing'):
            m.build(a,p)
        self.assertEqual(len(a.destroyed),3)


if __name__=='__main__':unittest.main()
