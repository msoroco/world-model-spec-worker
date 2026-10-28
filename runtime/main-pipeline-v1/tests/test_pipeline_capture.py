"""Tick ownership and measured telemetry of original-run capture, without CARLA."""
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch


class CaptureTests(unittest.TestCase):
    def test_same_frame_join_and_no_tick_or_setpoint_substitution(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            generator=root/'generator.py';generator.write_text('# fixture')
            class Collector:
                def __init__(self, client, actor, output, **kwargs):
                    self.output=output;output.mkdir(parents=True)
                    self.frames=(output/'frames.jsonl').open('w')
                def capture(self, frame, control, observed_evidence=None):
                    row={'frame':frame,'simulation_time':10.,'base':'base.pkl'}
                    self.frames.write(json.dumps(row)+'\n');return row
                def close(self):self.frames.close()
            vector=lambda x,y,z:types.SimpleNamespace(x=x,y=y,z=z)
            transform=types.SimpleNamespace(location=vector(1,2,3),rotation=types.SimpleNamespace(yaw=20),get_forward_vector=lambda:vector(1,0,0))
            control=types.SimpleNamespace(throttle=.7,steer=.1,brake=0.,hand_brake=False,reverse=False,manual_gear_shift=False,gear=1)
            ego=types.SimpleNamespace(id=7,type_id='vehicle.tesla.model3',attributes={'base_type':'car'},get_acceleration=lambda:vector(0,0,0),get_transform=lambda:transform,get_velocity=lambda:vector(3,4,0),get_control=lambda:control,
                bounding_box=types.SimpleNamespace(get_world_vertices=lambda t:[vector(x,y,z) for x in (0,2) for y in (1,3) for z in (0,2)]))
            weather=types.SimpleNamespace(**{k:0. for k in ('cloudiness','precipitation','precipitation_deposits','fog_density','fog_distance','sun_altitude_angle','wetness')})
            world=types.SimpleNamespace(get_actors=lambda:[ego],get_snapshot=lambda:types.SimpleNamespace(frame=42),
                get_map=lambda:types.SimpleNamespace(name='fixture',to_opendrive=lambda:'<OpenDRIVE/>',get_waypoint=lambda pos:None),get_weather=lambda:weather)
            calls=[]
            client=types.SimpleNamespace(get_world=lambda:world,
                start_recorder=lambda path,extra:(Path(path).write_bytes(b'recorder'),calls.append(('start',extra))),
                stop_recorder=lambda:calls.append(('stop',)),show_recorder_file_info=lambda path,extra:'Create 7: vehicle.tesla.model3')
            collector_module=types.ModuleType('scene_graph_collector');collector_module.SceneGraphCollector=Collector
            sgg_module=types.ModuleType('carla_sgg');native=types.ModuleType('carla_sgg.sgg');native.__file__=str(generator);native.copy_carla_vehicle_lights=lambda attrs,actor:None;sgg_module.sgg=native
            observation_path=Path(__file__).resolve().parents[1]/'python/original_observations.py'
            obs_spec=importlib.util.spec_from_file_location('original_observations',observation_path);observations=importlib.util.module_from_spec(obs_spec);obs_spec.loader.exec_module(observations)
            path=Path(__file__).resolve().parents[1]/'python/pipeline_capture.py'
            spec=importlib.util.spec_from_file_location('capture_under_test',path);module=importlib.util.module_from_spec(spec)
            with patch.dict('sys.modules',{'scene_graph_collector':collector_module,'carla_sgg':sgg_module,'carla_sgg.sgg':native,'original_observations':observations}):
                spec.loader.exec_module(module)
                capture=module.PipelineCapture(client,ego,root/'attempt','case')
                self.assertFalse(capture.visibility)
                with self.assertRaisesRegex(RuntimeError,'current original frame'):
                    capture.capture(41,0.)
                row=capture.capture(42,0.)
                self.assertEqual(row['speed_mps'],5.)
                self.assertEqual(row['position_m'],[1,2,3])
                capture.close();capture.close()
            self.assertEqual(calls,[('start',True),('stop',)])
            manifest=json.loads((root/'attempt/capture/manifest.json').read_text())
            self.assertTrue(manifest['extraction_confirmed'])
            event=json.loads((root/'attempt/capture/evidence.jsonl').read_text())
            self.assertEqual(event['original_frame'],event['replay_frame'])
            self.assertEqual(event['original_observations']['participants'][0]['speed_mps'],5.)
            self.assertEqual(event['original_observations']['participants'][0]['accel_longitudinal_mps2'],0.)
            self.assertEqual(event['ego']['speed_mps'],5.)
            self.assertEqual(event['ego']['speed_provenance'],'original_trace_actor_get_velocity')

    def test_visibility_requirements_override_optional_false_flag(self):
        import os
        path=Path(__file__).resolve().parents[1]/'python/pipeline_capture.py'
        spec=importlib.util.spec_from_file_location('capture_requirements_test',path)
        module=importlib.util.module_from_spec(spec)
        collector=types.ModuleType('scene_graph_collector');collector.SceneGraphCollector=object
        with patch.dict('sys.modules',{'scene_graph_collector':collector}):spec.loader.exec_module(module)
        with patch.dict(os.environ,{'SCENARIO_REQUIRED_CAPTURE_ATOMS':'["st.sight_distance"]'}):
            self.assertTrue(module.visibility_required())
        with patch.dict(os.environ,{'SCENARIO_REQUIRED_CAPTURE_ATOMS':'[]'}):
            self.assertFalse(module.visibility_required())
            self.assertTrue(module.visibility_required(['st.sight_distance']))
            self.assertFalse(module.visibility_required(['kin.speed']))
