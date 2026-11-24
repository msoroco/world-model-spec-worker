"""Tick-neutral original-run capture for generic scenario pipeline runners.

PipelineCapture(client, ego, output, case_id).capture(frame, time_s) must run
immediately after each world.tick(), once per trace/video frame. It owns
trace.jsonl and recorder capture, never ticks or changes the world/map/settings.
Call close() after the last sample, before destroying the ego or its sensors.
"""
import hashlib
import json
import math
import os
import time
from pathlib import Path
from scene_graph_collector import SceneGraphCollector


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def xyz(p):
    return [p.x, p.y, p.z]


def visibility_required(required_observations=(), requested=False):
    # Every common recording acquires sight; target-law dependencies cannot disable it.
    return True


class PipelineCapture:
    def __init__(self, client, ego, output, case_id, visibility=False, required_observations=(), physical_actor_registry=None):
        from traffic_spec_adapter.atom_contract import COMMON_CAPTURE_ATOMS
        requirements = set(COMMON_CAPTURE_ATOMS) | set(required_observations) | set(json.loads(os.environ.get('SCENARIO_REQUIRED_CAPTURE_ATOMS', '[]')))
        visibility = visibility_required(requirements, visibility)
        self.client, self.ego = client, ego
        self.world = client.get_world()
        self.output = Path(output).resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.capture_root = self.output/'capture'
        self.capture_root.mkdir(exist_ok=False)
        self.map = self.world.get_map()
        config_path=self.output/'config.json'
        config=json.loads(config_path.read_text()) if config_path.exists() else {}
        self.map_context={'declared_public_way_road_ids':config.get('public_way_road_ids',[]),
            'core_assumptions':config.get('authored_test_context',{}).get('core_assumptions',[])}
        (self.output/'road.xodr').write_text(self.map.to_opendrive())
        self.meta = {'status': 'draft', 'acquisition': 'original_live_run', 'case_id': case_id,
                     'source_run': str(self.output), 'map': self.map.name, 'frames': 0,
                     'required_observations': sorted(requirements),
                     'extraction_confirmed': False, 'sources': {},
                     'complete_driving_lanes': True,
                     'observation_contract_version': 5,
                     'road_user_visibility_observed': 'rel.visible' in requirements,
                     'speed_source': 'original live actor.get_velocity telemetry',
                     'frame_join': 'same original simulation frame; replay_* field names retained for adapter compatibility',
                     'visibility_scope': 'not measured' if not visibility else 'actual subject body rays; not ego-to-other visibility'}
        from original_observations import client_versions
        self.meta['native_client_versions'] = client_versions(client)
        from carla_sgg import sgg
        self.meta['generator_source'] = {'path': sgg.__file__, 'sha256': sha(sgg.__file__)}
        self.meta['source_components'] = {p.name:sha(p) for p in (Path(__file__),Path(__file__).with_name('scene_graph_collector.py'),Path(__file__).with_name('original_observations.py'),Path(__file__).with_name('native_graph_json.py'))}
        from traffic_spec_adapter import acceleration
        self.meta['acceleration_method'] = acceleration.METHOD
        self.meta['source_components']['acceleration.py'] = sha(acceleration.__file__)
        from traffic_spec_adapter import yaw_rate
        self.meta['yaw_rate_method'] = yaw_rate.METHOD
        self.meta['source_components']['yaw_rate.py'] = sha(yaw_rate.__file__)
        from carla_sgg import law_evidence
        self.meta['source_components']['law_evidence.py'] = sha(law_evidence.__file__)
        self.visibility_route_topology = law_evidence.modeled_observer_routes(self.map) if visibility else None
        self.visibility_lane_inventory = law_evidence.discover_driving_lanes(self.map) if visibility else None
        self.meta['visibility_acquisition'] = law_evidence.visibility_acquisition_contract() if visibility else None
        self.physical_registry=None
        if physical_actor_registry is not None:
            from traffic_spec_adapter.physical_actors import load_registry
            source=Path(physical_actor_registry);target=self.capture_root/'physical_actor_registry.json';target.write_bytes(source.read_bytes());self.physical_registry=load_registry(target)
            self.meta['physical_actor_registry']={'path':target.name,'sha256':sha(target)}
        self.closed = False
        self.visibility = visibility
        self.user_visibility = 'rel.visible' in requirements
        self.collector = None
        self.trace = None
        self.evidence = None
        self.recording = False
        self._manifest()
        try:
            if hasattr(self.map, 'generate_waypoints'):
                import carla
                junctions={}
                for waypoint in self.map.generate_waypoints(2.):
                    if waypoint.is_junction and waypoint.junction_id not in junctions:
                        junction=waypoint.get_junction()
                        junctions[junction.id]={'id':junction.id,
                            'body_vertices_m':[xyz(p) for p in junction.bounding_box.get_world_vertices(carla.Transform())],
                            'source':'native CARLA Junction.bounding_box; coarse map extent, not legal entry or a painted line'}
                facts={'map':self.map.name,'junctions':list(junctions.values()),
                       'crosswalk_vertices_m':[xyz(p) for p in self.map.get_crosswalks()],
                       'crosswalk_inventory_scope':'native Map.get_crosswalks metadata; additional rendered decals are not excluded'}
                from original_observations import map_control_inventory
                facts['native_control_inventory']=map_control_inventory(self.world)
                from original_observations import map_lane_topology
                facts['native_lane_topology']=map_lane_topology(self.map,self.output/'road.xodr')
                path=self.capture_root/'native_map_facts.json'
                path.write_text(json.dumps(facts,indent=2))
                self.meta['native_map_facts']={'path':path.name,'sha256':sha(path)}
            self.trace = (self.output/'trace.jsonl').open('x', buffering=1)
            self.evidence = (self.capture_root/'evidence.jsonl').open('x', buffering=1)
            self.client.start_recorder(str(self.output/'carla_recorder.log'), True)
            self.recording = True
            self.collector = SceneGraphCollector(client, ego.id, self.capture_root/'native',
                save_base=True, include_static_props=True, complete_driving_lanes=True)
        except BaseException:
            self.close(confirmed=False)
            raise

    def _manifest(self):
        (self.capture_root/'manifest.json').write_text(json.dumps(self.meta, indent=2))

    def capture(self, frame, time_s, extra=None):
        if self.closed or self.world.get_snapshot().frame != frame:
            raise RuntimeError('Capture must observe the current original frame')
        transform = self.ego.get_transform()
        velocity = self.ego.get_velocity()
        speed = math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
        c = self.ego.get_control()
        control = {k: getattr(c, k) for k in ('throttle','steer','brake','hand_brake','reverse','manual_gear_shift','gear')}
        pos = xyz(transform.location)
        row = {'frame': frame, 'time_s': time_s, 'position': dict(zip(('x','y','z'), pos)),
               'position_m': pos, 'heading_deg': transform.rotation.yaw,
               'speed_mps': speed, 'speed_mph': speed/.44704,
               'velocity_mps': xyz(velocity), 'control': control}
        if extra:
            if set(extra) & set(row):
                raise ValueError('Extra observations cannot overwrite measured telemetry')
            row.update(extra)
        observation_started=time.perf_counter()
        from original_observations import observe
        original_observations = observe(self.world, self.ego, frame, time_s, self.user_visibility,self.physical_registry)
        original_observations['map_context']=self.map_context
        subject_observation = next(a for a in original_observations['participants'] if a['actor_id'] == self.ego.id)
        if 'accel_longitudinal_mps2' in subject_observation:
            row['accel_longitudinal_mps2'] = subject_observation['accel_longitudinal_mps2']
        row['acceleration_method'] = subject_observation['acceleration_method']
        row['acceleration_projection'] = subject_observation['acceleration_projection']
        row['acceleration_mps2'] = subject_observation['acceleration_mps2']
        row['forward_vector'] = subject_observation['forward_vector']
        for key in ('wheel_angle_method', 'wheel_angle_references', 'wheel_steer_angles_deg', 'wheel_angle_errors'):
            if key in subject_observation:
                row[key] = subject_observation[key]
        observation_seconds=time.perf_counter()-observation_started
        record = self.collector.capture(frame, c, observed_evidence=original_observations)
        if not record:
            raise RuntimeError('Missing original graph frame')
        visibility = None
        if self.visibility:
            from carla_sgg.law_evidence import actor_visibility
            visibility = actor_visibility(self.world, self.ego, mapping=self.map,
                                          lane_inventory=self.visibility_lane_inventory,
                                          route_topology=self.visibility_route_topology)
        wp = self.map.get_waypoint(transform.location)
        weather = self.world.get_weather()
        event = {'original_frame': frame, 'replay_frame': frame, 'actor_id': self.ego.id,
                 'recording_time_s': time_s, 'replay_simulation_time_s': record['simulation_time'],
                 'ego': {'position_m': pos, 'heading_deg': transform.rotation.yaw,
                         'speed_mps': speed, 'speed_provenance': 'original_trace_actor_get_velocity',
                         'body_vertices_m': [xyz(p) for p in self.ego.bounding_box.get_world_vertices(transform)]},
                 'world': {'weather': {k: getattr(weather,k) for k in ('cloudiness','precipitation','precipitation_deposits','fog_density','fog_distance','sun_altitude_angle','wetness')},
                           'road_projection': None if wp is None else {'road_id': wp.road_id,'section_id':wp.section_id,'lane_id':wp.lane_id,'s_m':wp.s}},
                 'original_observations': original_observations,
                 'timing':{'observation_seconds':observation_seconds,'graph_capture_seconds':record.get('capture_seconds'),'graph_extraction_seconds':record.get('extraction_seconds')},
                 'visibility': visibility, 'supporting_only': {'applied_control': control}}
        self.trace.write(json.dumps(row)+'\n')
        self.evidence.write(json.dumps(event)+'\n')
        self.meta['frames'] += 1
        return row

    def close(self, confirmed=True):
        if self.closed:
            return
        self.closed = True
        try:
            if self.recording:
                self.client.stop_recorder()
                self.recording = False
            if self.collector:
                self.collector.close()
            if self.trace:
                self.trace.close()
            if self.evidence:
                self.evidence.close()
            recorder = self.output/'carla_recorder.log'
            if recorder.exists():
                info = self.client.show_recorder_file_info(str(recorder), True)
                (self.capture_root/'recorder_info.txt').write_text(info)
            for name in ('road.xodr','trace.jsonl','carla_recorder.log'):
                if (self.output/name).is_file():
                    self.meta['sources'][name] = sha(self.output/name)
            self.meta['extraction_confirmed'] = bool(confirmed and self.meta['frames'] and
                len(self.meta['sources']) == 3 and (self.capture_root/'recorder_info.txt').exists())
        finally:
            self._manifest()

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        self.close(confirmed=kind is None)
