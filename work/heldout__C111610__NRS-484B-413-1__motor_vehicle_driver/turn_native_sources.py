"""Retain exact Native turn, participant, lamp and listener PCM originals.

The caller must supply audio packets from an actual listener capture. A control
command or a synthetic horn flag is never converted into audio evidence here.
"""
from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path


def _finite(value, label):
    value = float(value)
    if not isfinite(value):
        raise ValueError('Nonfinite original ' + label)
    return value


def _geometry(actor):
    transform = actor.get_transform()
    location = transform.location
    box = actor.bounding_box
    x = _finite(location.x, 'actor x')
    y = _finite(location.y, 'actor y')
    radius = hypot(_finite(box.extent.x, 'body x extent'),
                   _finite(box.extent.y, 'body y extent'))
    if radius <= 0:
        raise ValueError('Original Native body radius is zero')
    return {'x_m': x, 'y_m': y, 'body_radius_m': radius}


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


class TurnSourceRecorder:
    """Write synchronized originals; caller owns actor and audio lifetimes."""
    def __init__(self, root, ego, participants, listener_id, context,
                 left_light_mask, right_light_mask):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ego = ego
        self.participants = dict(participants)
        self.listener_id = str(listener_id)
        self.left_mask = int(left_light_mask)
        self.right_mask = int(right_light_mask)
        if not self.listener_id or self.listener_id not in self.participants:
            raise ValueError('Listener needs a retained Native participant')
        if not self.left_mask or not self.right_mask or self.left_mask == self.right_mask:
            raise ValueError('Native left/right light masks required')
        expected = set(context.get('participant_types', {}))
        if expected != set(self.participants):
            raise ValueError('Affected context differs from Native participants')
        for key in ('pedestrian_may_be_affected', 'vehicle_may_be_affected'):
            if type(context.get(key)) is not bool or not context.get(key + '_source'):
                raise ValueError('Affected status needs a separate reviewed source')
        if not context.get('listener_position_source') or not context.get('participant_geometry_source'):
            raise ValueError('Listener and participant geometry need original provenance')
        self.context = dict(context, listener_id=self.listener_id)
        _write_json(self.root / 'affected_participants.json', self.context)
        self.streams = {name: (self.root / name).open('w') for name in
                        ('ego_turn_motion.jsonl', 'ego_signal_audio.jsonl',
                         'participant_bodies.jsonl', 'listener_audio_original.jsonl')}
        self.previous = None
        self.count = 0

    def append(self, frame, time_s, audio_packet):
        if type(frame) is not int or frame < 0:
            raise ValueError('Native frame identity required')
        time_s = _finite(time_s, 'frame time')
        if self.previous is not None:
            prior_frame, prior_time = self.previous
            if frame != prior_frame + 1 or abs(time_s - prior_time - .05) > 1e-4:
                raise ValueError('Native source frames are not joined at 20 Hz')
        no_pedestrian_audio = audio_packet is None and not self.context['pedestrian_may_be_affected']
        if not no_pedestrian_audio:
            if not isinstance(audio_packet, dict) or audio_packet.get('origin') != 'listener_pcm_capture':
                raise ValueError('Original listener PCM packet required; command state is insufficient')
            if audio_packet.get('frame') != frame or audio_packet.get('listener_id') != self.listener_id:
                raise ValueError('Listener PCM packet frame or identity differs')
            samples = audio_packet.get('samples')
            if not isinstance(samples, list) or len(samples) < 8:
                raise ValueError('Listener PCM packet lacks source samples')
            samples = [_finite(sample, 'listener PCM sample') for sample in samples]
            if any(abs(sample) > 1 for sample in samples):
                raise ValueError('Listener PCM sample outside normalized range')
            if not audio_packet.get('capture_source'):
                raise ValueError('Listener PCM capture source is uncited')
        else:
            samples = None
        ego = _geometry(self.ego)
        yaw = _finite(self.ego.get_transform().rotation.yaw, 'ego yaw')
        bodies = {ident: _geometry(actor) for ident, actor in self.participants.items()}
        if not callable(getattr(self.ego, 'get_light_state', None)):
            raise ValueError('Native light-state readback unavailable')
        lights = int(self.ego.get_light_state())
        left = bool(lights & self.left_mask)
        right = bool(lights & self.right_mask)
        if left and right:
            raise ValueError('Ambiguous Native indicator readback')
        indicator = 'left' if left else 'right' if right else 'off'
        packet = (dict(audio_packet, samples=samples) if not no_pedestrian_audio else
                  {'origin': 'not_collected_no_affected_pedestrian', 'frame': frame,
                   'listener_id': self.listener_id, 'samples': None})
        packet['sha256'] = (sha256(json.dumps(samples, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
                            if samples is not None else None)
        rows = {
            'ego_turn_motion.jsonl': dict(frame=frame, time_s=time_s, ego_yaw_deg=yaw, **ego),
            'ego_signal_audio.jsonl': {'frame': frame, 'time_s': time_s,
                                       'listener_id': self.listener_id,
                                       'indicator_readback': indicator,
                                       'listener_audio_samples': samples,
                                       'listener_audio_status': ('not_collected_no_affected_pedestrian'
                                                                 if no_pedestrian_audio else 'original_pcm'),
                                       'listener_packet_sha256': packet['sha256']},
            'participant_bodies.jsonl': {'frame': frame, 'time_s': time_s, 'bodies': bodies},
            'listener_audio_original.jsonl': packet,
        }
        for name, row in rows.items():
            self.streams[name].write(json.dumps(row, allow_nan=False) + '\n')
        self.previous = frame, time_s
        self.count += 1

    def close(self):
        for stream in self.streams.values():
            stream.close()
        if self.count < 3:
            raise ValueError('Native turn source capture has fewer than three frames')
        manifest = {'format': 'worker-turn-original-source-manifest', 'frames': self.count,
                    'listener_id': self.listener_id, 'source_kind': 'native_plus_listener_pcm',
                    'sources': {name: sha256((self.root / name).read_bytes()).hexdigest()
                                for name in (*self.streams, 'affected_participants.json')}}
        _write_json(self.root / 'turn-source-manifest.json', manifest)
        return manifest
