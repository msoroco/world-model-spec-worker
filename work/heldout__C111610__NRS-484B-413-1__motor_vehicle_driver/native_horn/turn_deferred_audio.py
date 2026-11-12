"""Retain Native turn originals before a separately captured listener WAV is sealed."""
from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path
from types import SimpleNamespace

from listener_pcm_source import ListenerPcmSource
from turn_native_sources import TurnSourceRecorder


def finite(value, label):
    value = float(value)
    if not isfinite(value):
        raise ValueError('Nonfinite Native ' + label)
    return value


def snapshot_actor(actor):
    transform = actor.get_transform()
    location = transform.location
    extent = actor.bounding_box.extent
    x, y = finite(location.x, 'actor x'), finite(location.y, 'actor y')
    ex, ey = finite(extent.x, 'actor extent x'), finite(extent.y, 'actor extent y')
    if hypot(ex, ey) <= 0:
        raise ValueError('Native actor body radius is zero')
    return {'x_m': x, 'y_m': y, 'extent_x_m': ex, 'extent_y_m': ey,
            'yaw_deg': finite(transform.rotation.yaw, 'actor yaw')}


def proxy_actor(body, light_state=0):
    transform = SimpleNamespace(
        location=SimpleNamespace(x=body['x_m'], y=body['y_m']),
        rotation=SimpleNamespace(yaw=body['yaw_deg']))
    extent = SimpleNamespace(x=body['extent_x_m'], y=body['extent_y_m'])
    return SimpleNamespace(get_transform=lambda: transform,
                           bounding_box=SimpleNamespace(extent=extent),
                           get_light_state=lambda: light_state)


class DeferredTurnSourceRecorder:
    """Write original Native snapshots first, then join captured listener PCM."""
    def __init__(self, root, ego, participants, listener_id, context,
                 left_light_mask, right_light_mask):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ego = ego
        self.participants = dict(participants)
        self.listener_id = str(listener_id)
        self.context = dict(context)
        self.left_mask = int(left_light_mask)
        self.right_mask = int(right_light_mask)
        if not self.context.get('pedestrian_may_be_affected'):
            raise ValueError('Deferred listener capture requires an affected pedestrian')
        if not self.listener_id or self.listener_id not in self.participants:
            raise ValueError('Deferred listener needs a retained participant')
        if set(self.context.get('participant_types', {})) != set(self.participants):
            raise ValueError('Deferred listener participant identities differ')
        self.raw_path = self.root / 'native_turn_pre_audio.jsonl'
        if self.raw_path.exists():
            raise ValueError('Native pre-audio source already exists')
        self.stream = self.raw_path.open('w')
        self.count = 0
        self.previous = None

    def append(self, frame, time_s):
        if type(frame) is not int or frame < 0:
            raise ValueError('Native frame identity required')
        time_s = finite(time_s, 'frame time')
        if self.previous is not None:
            last_frame, last_time = self.previous
            if frame != last_frame + 1 or abs(time_s - last_time - .05) > 1e-4:
                raise ValueError('Deferred Native source frames are not joined at 20 Hz')
        lights = int(self.ego.get_light_state())
        if lights & self.left_mask and lights & self.right_mask:
            raise ValueError('Ambiguous Native indicator readback')
        row = {'frame': frame, 'time_s': time_s,
               'ego': snapshot_actor(self.ego), 'light_state': lights,
               'participants': {ident: snapshot_actor(actor)
                                for ident, actor in self.participants.items()}}
        self.stream.write(json.dumps(row, allow_nan=False) + '\n')
        self.stream.flush()
        self.count += 1
        self.previous = frame, time_s

    def close_raw(self):
        self.stream.close()
        if self.count < 3:
            raise ValueError('Deferred Native turn has fewer than three frames')
        return sha256(self.raw_path.read_bytes()).hexdigest()

    def finalize_audio(self, wav_path, *, source_start_time_s, capture_provenance):
        if not self.stream.closed:
            raise ValueError('Close Native source before joining listener audio')
        rows = [json.loads(line) for line in self.raw_path.read_text().splitlines()]
        if len(rows) != self.count:
            raise ValueError('Native pre-audio source frame count changed')
        first_frame = rows[0]['frame']
        pcm = ListenerPcmSource(wav_path, self.listener_id, first_frame=first_frame,
                                source_start_time_s=source_start_time_s,
                                capture_provenance=capture_provenance)
        writer = TurnSourceRecorder(
            self.root, proxy_actor(rows[0]['ego']),
            {ident: proxy_actor(body) for ident, body in rows[0]['participants'].items()},
            self.listener_id, self.context, self.left_mask, self.right_mask)
        try:
            for row in rows:
                writer.ego = proxy_actor(row['ego'], row['light_state'])
                writer.participants = {ident: proxy_actor(body)
                                       for ident, body in row['participants'].items()}
                packet = pcm.packet(row['frame'], row['time_s'])
                writer.append(row['frame'], row['time_s'], packet)
            manifest = writer.close()
        finally:
            pcm.close()
            for stream in writer.streams.values():
                if not stream.closed:
                    stream.close()
        manifest['native_pre_audio_sha256'] = sha256(self.raw_path.read_bytes()).hexdigest()
        manifest['listener_wav_sha256'] = sha256(Path(wav_path).read_bytes()).hexdigest()
        (self.root / 'turn-source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        return manifest
