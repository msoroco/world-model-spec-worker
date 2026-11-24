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
            import os
            path=Path(os.environ.get('PIPELINE_CAPTURE_SOURCE',Path(__file__).resolve().parents[1]/'python/pipeline_capture.py'))
            spec=importlib.util.spec_from_file_location('capture_under_test',path);module=importlib.util.module_from_spec(spec)
            law_evidence=types.ModuleType('carla_sgg.law_evidence');law_evidence.__file__=str(generator);visibility_calls=[]
            law_evidence.actor_visibility=lambda *a,**k:visibility_calls.append(k) or None
            route_model={'fixture_route_model':True};lane_inventory={}
            law_evidence.modeled_observer_routes=lambda mapping:route_model
            law_evidence.discover_driving_lanes=lambda mapping:lane_inventory
            law_evidence.visibility_acquisition_contract=lambda:{'capability_method':'estimate:vehicle_reference_geometry','measurement_method':'actual_actor_body_raycast_v3'}
            with patch.dict('sys.modules',{'carla_sgg.law_evidence':law_evidence,'scene_graph_collector':collector_module,'carla_sgg':sgg_module,'carla_sgg.sgg':native,'original_observations':observations}):
                spec.loader.exec_module(module)
                capture=module.PipelineCapture(client,ego,root/'attempt','case')
                self.assertTrue(capture.visibility)
                with self.assertRaisesRegex(RuntimeError,'current original frame'):
                    capture.capture(41,0.)
                row=capture.capture(42,0.)
                self.assertEqual(row['speed_mps'],5.)
                from traffic_spec_adapter.acceleration import METHOD
                self.assertEqual(row['acceleration_method'],METHOD)
                self.assertEqual(row['acceleration_projection']['value_mps2'],0.)
                self.assertEqual(row['position_m'],[1,2,3])
                capture.close();capture.close()
            self.assertEqual(calls,[('start',True),('stop',)])
            manifest=json.loads((root/'attempt/capture/manifest.json').read_text())
            self.assertTrue(manifest['extraction_confirmed'])
            self.assertEqual(manifest['acceleration_method'],METHOD)
            self.assertIn('acceleration.py',manifest['source_components'])
            self.assertEqual(manifest['visibility_acquisition']['capability_method'],'estimate:vehicle_reference_geometry')
            self.assertIs(visibility_calls[0]['route_topology'],route_model)
            self.assertIs(visibility_calls[0]['lane_inventory'],lane_inventory)
            event=json.loads((root/'attempt/capture/evidence.jsonl').read_text())
            self.assertEqual(event['original_frame'],event['replay_frame'])
            self.assertEqual(event['original_observations']['participants'][0]['speed_mps'],5.)
            self.assertEqual(event['original_observations']['participants'][0]['accel_longitudinal_mps2'],0.)
            self.assertIn('stop waypoints and trigger geometry', event['original_observations']['control_inventory'])
            self.assertEqual(event['ego']['speed_mps'],5.)
            self.assertEqual(event['ego']['speed_provenance'],'original_trace_actor_get_velocity')

    def test_native_control_geometry_is_recorded_without_controller_inference(self):
        path=Path(__file__).resolve().parents[1]/'python/original_observations.py'
        spec=importlib.util.spec_from_file_location('original_controls_under_test',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        vector=lambda x,y,z:types.SimpleNamespace(x=x,y=y,z=z)
        transform=types.SimpleNamespace(location=vector(0,0,0))
        waypoint=types.SimpleNamespace(road_id=2,section_id=0,lane_id=-1,s=11.5,
            transform=types.SimpleNamespace(location=vector(11.5,1,0)),
            is_junction=False,junction_id=-1)
        light=types.SimpleNamespace(id=5,type_id='traffic.traffic_light',get_transform=lambda:transform,
            get_stop_waypoints=lambda:[waypoint],get_affected_lane_waypoints=lambda:[waypoint])
        sign=types.SimpleNamespace(id=6,type_id='traffic.stop',get_transform=lambda:transform,
            trigger_volume=types.SimpleNamespace(get_world_vertices=lambda t:
                [vector(x,y,z) for x in (0,2) for y in (0,2) for z in (0,1)]))
        self.assertEqual(module.device_state(light)['stop_waypoints'][0]['position_m'],[11.5,1,0])
        self.assertEqual(len(module.device_state(sign)['trigger_vertices_m']),8)
        del sign.trigger_volume
        self.assertIn('trigger_volume',module.device_state(sign)['observation_errors'])

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
            self.assertTrue(module.visibility_required())
            self.assertTrue(module.visibility_required(['st.sight_distance']))
            self.assertTrue(module.visibility_required(['kin.speed']))

class WheelReadbackTests(unittest.TestCase):
    def test_pair_readbacks_and_failure_are_preserved_without_fallback(self):
        path = Path(__file__).resolve().parents[1]/'python/original_observations.py'
        spec = importlib.util.spec_from_file_location('wheel_capture_test', path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        carla = types.ModuleType('carla')
        carla.VehicleWheelLocation = types.SimpleNamespace(FL_Wheel='left', FR_Wheel='right', Front_Wheel='front')
        actor = types.SimpleNamespace(type_id='vehicle.test', attributes={'number_of_wheels':'4'})
        vector = lambda x,y,z: types.SimpleNamespace(x=x,y=y,z=z)
        transform = types.SimpleNamespace(location=vector(0,0,0),rotation=types.SimpleNamespace(yaw=0),get_forward_vector=lambda:vector(1,0,0))
        actor.id=1; actor.get_transform=lambda:transform
        actor.get_velocity=lambda:vector(0,0,0); actor.get_acceleration=lambda:vector(0,0,0)
        actor.bounding_box=types.SimpleNamespace(get_world_vertices=lambda t:[])
        native=types.ModuleType('carla_sgg.sgg');native.copy_carla_vehicle_lights=lambda d,a:None
        actor.get_wheel_steer_angle=lambda wheel:{'left':-25.,'right':-20.}[wheel]
        with patch.dict('sys.modules', {'carla':carla,'carla_sgg.sgg':native}):
            value=module.actor_state(actor)
            self.assertEqual(value['wheel_steer_angles_deg'], {'front_left':-25.,'front_right':-20.})
            actor.get_wheel_steer_angle=lambda wheel: float('nan') if wheel=='right' else -25.
            value=module.actor_state(actor)
            self.assertEqual(value['wheel_steer_angles_deg'], {'front_left':-25.})
            self.assertIn('front_right',value['wheel_angle_errors'])
            self.assertNotIn('wheel_steer_angle_deg',value)


class NativeControlInventoryTests(unittest.TestCase):
    def module(self):
        path=Path(__file__).resolve().parents[1]/'python/original_observations.py'
        spec=importlib.util.spec_from_file_location('native_inventory_test',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_partial_environment_geometry_failure_retains_identity_and_no_absence_claim(self):
        module=self.module();vector=lambda x,y,z:types.SimpleNamespace(x=x,y=y,z=z)
        rotation=types.SimpleNamespace(pitch=0,yaw=0,roll=0)
        box=types.SimpleNamespace(location=vector(0,0,0),extent=vector(1,1,1),rotation=rotation,
                                  get_local_vertices=lambda:[vector(0,0,0),vector(1,1,1)])
        transform=types.SimpleNamespace(location=vector(0,0,0),rotation=rotation)
        good=types.SimpleNamespace(id=1,name='native-sign',transform=transform,bounding_box=box)
        bad=types.SimpleNamespace(id=2,name='native-unreadable',transform=transform)
        world=types.SimpleNamespace(get_environment_objects=lambda label:[good,bad]if label=='signs'else[],
                                    get_map=lambda:types.SimpleNamespace(get_all_landmarks=lambda:[]))
        carla=types.ModuleType('carla');carla.CityObjectLabel=types.SimpleNamespace(TrafficSigns='signs',TrafficLight='lights')
        with patch.dict('sys.modules',{'carla':carla}):result=module.map_control_inventory(world)
        signs=result['environment_queries']['TrafficSigns']
        self.assertTrue(signs['query_complete'])
        self.assertEqual([entry['native_id']for entry in signs['objects']],[1,2])
        self.assertIn('geometry',signs['objects'][1]['observation_errors'])
        self.assertFalse(result['physical_absence_verified'])
        self.assertIsNone(signs['objects'][0]['enabled'])
        self.assertEqual(result['environment_queries']['TrafficLight']['objects'],[])
        self.assertFalse(result['physical_absence_verified'])

    def test_state_failure_keeps_actor_and_each_head_and_removes_stale_native_state(self):
        import networkx as nx
        module=self.module();vector=lambda x,y,z:types.SimpleNamespace(x=x,y=y,z=z)
        def failed():raise RuntimeError('native state read failed')
        actor=types.SimpleNamespace(id=5,type_id='traffic.traffic_light',
            get_transform=lambda:types.SimpleNamespace(location=vector(0,0,0)),get_state=failed,
            get_light_boxes=lambda:[],get_stop_waypoints=lambda:[])
        record=module.device_state(actor)
        self.assertEqual(record['actor_id'],5)
        self.assertNotIn('state',record)
        self.assertIn('state',record['observation_errors'])
        self.assertEqual(record['light_boxes'],[])
        graph=nx.DiGraph();graph.add_node('head',sem_class='traffic.traffic_light',carla_id=5,light_state='Green')
        module.merge_graph(graph,{'participants':[],'devices':[record]})
        self.assertNotIn('light_state',graph.nodes['head'])
        self.assertEqual(graph.nodes['head']['original_device_observation'],record)
