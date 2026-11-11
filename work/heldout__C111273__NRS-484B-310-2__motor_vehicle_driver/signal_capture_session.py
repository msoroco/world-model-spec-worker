"""Retain original Native signal and participant samples at each camera joined tick."""
import json
from math import hypot
from pathlib import Path


def _state(actor):
    if actor is None or not actor.is_alive:
        raise ValueError('required participant absent from Native world')
    p = actor.get_transform().location
    v = actor.get_velocity()
    return {'actor_id': int(actor.id), 'center_xy': [float(p.x), float(p.y)],
            'speed_mps': hypot(v.x, v.y)}


class SignalCaptureSession:
    def __init__(self, output, pipeline_capture, scene, context):
        from worker_exchange.native_output import FrameMap
        root = Path(output)
        if not context.get('official_control_source'):
            raise ValueError('official-control premise requires a source record')
        if context.get('selected_direction') != scene['selected'].direction:
            raise ValueError('selected governed direction differs')
        if context.get('opendrive_id') != scene['selected'].opendrive_id:
            raise ValueError('source OpenDRIVE ID differs')
        for name in ('signal_context.json', 'signal_state.jsonl',
                     'participant_state.jsonl', 'video_frames.jsonl'):
            if (root/name).exists():
                raise ValueError('retain prior source; use fresh attempt: ' + name)
        (root/'signal_context.json').write_text(json.dumps(context, indent=2)+'\n')
        self.signal = (root/'signal_state.jsonl').open('x')
        self.participants = (root/'participant_state.jsonl').open('x')
        self.frames = FrameMap(root/'video_frames.jsonl')
        self.pipeline = pipeline_capture
        self.scene = scene
        self.closed = False

    def capture(self, frame, time_s, flash_row):
        if self.closed:
            raise ValueError('capture session closed')
        if flash_row['light_actor_id'] != self.scene['light'].id:
            raise ValueError('flashing controller belongs to another head')
        original = self.pipeline.capture(frame, time_s)
        if (original.get('frame'), original.get('time_s')) != (frame, time_s):
            raise ValueError('PipelineCapture returned another original tick')
        signal = {'frame': frame, 'time_s': time_s,
                  'light_actor_id': flash_row['light_actor_id'],
                  'opendrive_id': self.scene['selected'].opendrive_id,
                  'yellow_commanded': flash_row['yellow_commanded'],
                  'native_light_state': flash_row['native_light_state'],
                  'lens_pixel_visible': None}
        participants = {'frame': frame, 'time_s': time_s,
                        'ego': _state(self.scene['ego']),
                        'crossing': (_state(self.scene['crossing'])
                                     if self.scene['crossing'] is not None else None)}
        self.signal.write(json.dumps(signal)+'\n'); self.signal.flush()
        self.participants.write(json.dumps(participants)+'\n'); self.participants.flush()
        self.frames.append(frame, time_s)
        return original

    def close(self):
        if not self.closed:
            self.closed = True
            self.frames.close(); self.signal.close(); self.participants.close()
