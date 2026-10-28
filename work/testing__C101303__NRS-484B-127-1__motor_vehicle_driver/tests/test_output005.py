import unittest
import runner

class CaptureWriterTests(unittest.TestCase):
    def test_runner_calls_frame_writer_with_original_tick(self):
        class Map:
            def __init__(self): self.calls=[]
            def append(self,*args): self.calls.append(args);return {"carla_frame":args[0]}
        mapping=Map()
        row=runner.capture_frame_identity(mapping,21714,0.05)
        self.assertEqual(mapping.calls,[(21714,0.05)])
        self.assertEqual(row["carla_frame"],21714)

    def test_actual_frame_map_rejects_duplicate(self):
        import tempfile
        from pathlib import Path
        from worker_exchange.native_output import FrameMap
        with tempfile.TemporaryDirectory() as root:
            with FrameMap(Path(root)/"video_frames.jsonl") as mapping:
                mapping.append(10,0.05)
                with self.assertRaises(ValueError): mapping.append(10,0.10)

class CleanupAndRestoreTests(unittest.TestCase):
    def test_failed_cleanup_does_not_skip_restoration(self):
        calls=[];errors=[]
        def fail():
            calls.append('failed_action')
            raise RuntimeError('sensor stop failed')
        runner.cleanup_action(errors,'sensor_stop',fail)
        runner.cleanup_action(errors,'world_restore',lambda:calls.append('restore'))
        self.assertEqual(calls,['failed_action','restore'])
        self.assertEqual(errors[0]['action'],'sensor_stop')

    def test_packaged_generated_and_failed_readback(self):
        from types import SimpleNamespace as N
        from worker_exchange.world_restore import snapshot,restore
        class World:
            def __init__(self,name='OpenDriveMap',xodr='source'):
                self.name=name;self.xodr=xodr
                self.settings=N(synchronous_mode=False,fixed_delta_seconds=None)
                self.weather=N(cloudiness=1.0)
            def get_map(self):return N(name=self.name,to_opendrive=lambda:self.xodr)
            def get_settings(self):return self.settings
            def get_weather(self):return self.weather
            def apply_settings(self,value):self.settings=value
            def set_weather(self,value):self.weather=value
        class Client:
            def __init__(self,name):self.world=World(name);self.calls=[]
            def get_world(self):return self.world
            def get_available_maps(self):return ['Town01']
            def load_world(self,name):self.calls.append('load');self.world=World(name)
            def generate_opendrive_world(self,x):self.calls.append('generate');self.world=World(xodr=x)
        for name,expected in [('Town01','load'),('OpenDriveMap','generate')]:
            client=Client(name);saved=snapshot(client);client.world=World(xodr='changed')
            self.assertTrue(restore(client,saved)['restored'])
            self.assertEqual(client.calls,[expected])
        client=Client('OpenDriveMap');saved=snapshot(client)
        client.generate_opendrive_world=lambda x:None
        client.world=World(xodr='changed')
        with self.assertRaisesRegex(ValueError,'OpenDRIVE'):
            restore(client,saved)
