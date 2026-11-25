"""Original walker graph/evidence capture for the pinned Core handoff.

This adapter observes the actual WalkerControl and actor state on each Native
frame. It does not project a walker command onto vehicle pedal fields.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _xyz(value):
    return [float(value.x), float(value.y), float(value.z)]


class PedestrianGraphSink:
    def __init__(self, client, actor, output, case_id):
        from scene_graph_collector import SceneGraphCollector
        self.client, self.actor = client, actor
        self.world = client.get_world()
        self.output = Path(output).resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.capture_root = self.output / 'capture'
        self.capture_root.mkdir(exist_ok=False)
        self.frames = 0
        self.closed = False
        self.recording = False
        self.meta = {
            'status': 'draft', 'acquisition': 'original_live_run',
            'case_id': case_id, 'source_run': str(self.output),
            'map': self.world.get_map().name, 'frames': 0,
            'required_observations': [], 'extraction_confirmed': False,
            'sources': {}, 'complete_driving_lanes': True,
            'observation_contract_version': 5,
            'frame_join': 'same original synchronous Native frame',
            'ego_actor_type': actor.type_id,
            'ego_control_source': 'original WalkerControl direction, speed, jump',
        }
        if not actor.type_id.startswith('walker.pedestrian.'):
            raise ValueError('pedestrian graph sink requires original walker')
        (self.output / 'road.xodr').write_text(self.world.get_map().to_opendrive())
        (self.capture_root / 'manifest.json').write_text(json.dumps(self.meta, indent=2) + '\n')
        self.trace = (self.output / 'trace.jsonl').open('x')
        self.evidence = (self.capture_root / 'evidence.jsonl').open('x')
        try:
            self.client.start_recorder(str(self.output / 'carla_recorder.log'), True)
            self.recording = True
            self.collector = SceneGraphCollector(
                client, actor.id, self.capture_root / 'native',
                save_base=True, include_static_props=True,
                complete_driving_lanes=True)
        except BaseException:
            self.close(confirmed=False)
            raise

    def capture(self, crossing_row):
        from original_observations import observe
        if self.closed:
            raise ValueError('original graph sink already closed')
        frame = crossing_row['frame']
        if self.world.get_snapshot().frame != frame:
            raise ValueError('original walker graph frame differs')
        time_s = crossing_row['elapsed_seconds']
        actor = self.actor
        transform = actor.get_transform()
        velocity = actor.get_velocity()
        control = actor.get_control()
        command = {'direction': _xyz(control.direction),
                   'speed': float(control.speed), 'jump': bool(control.jump)}
        observation = observe(self.world, actor, frame, time_s)
        subject = next((item for item in observation['participants']
                        if item['actor_id'] == actor.id), None)
        if subject is None or subject['blueprint'] != actor.type_id:
            raise ValueError('original walker participant missing')
        graph = self.collector.capture(frame, control,
                                       observed_evidence=observation)
        if not graph:
            raise ValueError('original walker adapter graph missing')
        trace = {
            'frame': frame, 'time_s': time_s,
            'position': dict(zip(('x', 'y', 'z'), _xyz(transform.location))),
            'position_m': _xyz(transform.location),
            'heading_deg': float(transform.rotation.yaw),
            'speed_mps': subject['speed_mps'],
            'speed_mph': subject['speed_mps'] / .44704,
            'velocity_mps': _xyz(velocity),
            'control': {'walker': command},
            'pedestrian_signal': {'official_signal_head_id': crossing_row['official_signal_head_id'],
                                  'lit_aspects': crossing_row['lit_aspects'],
                                  'other_device_id': crossing_row['other_device_id'],
                                  'other_device_mode': crossing_row['other_device_mode']},
        }
        event = {
            'original_frame': frame, 'replay_frame': frame,
            'actor_id': actor.id, 'recording_time_s': time_s,
            'replay_simulation_time_s': graph['simulation_time'],
            'ego': {'position_m': subject['position_m'],
                    'heading_deg': subject['heading_deg'],
                    'speed_mps': subject['speed_mps'],
                    'speed_provenance': 'original_trace_actor_get_velocity',
                    'body_vertices_m': subject['body_vertices_m']},
            'original_observations': observation,
            'world': {'weather': {}},
            'supporting_only': {'applied_walker_control': command},
        }
        self.trace.write(json.dumps(trace, allow_nan=False) + '\n')
        self.evidence.write(json.dumps(event, allow_nan=False) + '\n')
        self.frames += 1

    def close(self, confirmed=True):
        if self.closed:
            return
        self.closed = True
        if self.recording:
            self.client.stop_recorder()
            self.recording = False
        if hasattr(self, 'collector'):
            self.collector.close()
        self.trace.close()
        self.evidence.close()
        recorder = self.output / 'carla_recorder.log'
        if recorder.is_file():
            info = self.client.show_recorder_file_info(str(recorder), True)
            (self.capture_root / 'recorder_info.txt').write_text(info)
        for name in ('road.xodr', 'trace.jsonl', 'carla_recorder.log'):
            if (self.output / name).is_file():
                self.meta['sources'][name] = _sha(self.output / name)
        self.meta['frames'] = self.frames
        self.meta['extraction_confirmed'] = bool(
            confirmed and self.frames == 900 and len(self.meta['sources']) == 3 and
            (self.capture_root / 'recorder_info.txt').is_file())
        self.meta['status'] = 'captured' if self.meta['extraction_confirmed'] else 'incomplete'
        (self.capture_root / 'manifest.json').write_text(json.dumps(self.meta, indent=2) + '\n')
