"""Live pedestrian-location microphone acquisition and saved-source checks.

The device placement is a separate original-source review. A controller request
is never substituted for microphone samples.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import time

RATE = 8000
CHANNELS = 1
BYTES_PER_SAMPLE = 2


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_pcm(output, metadata):
    source=Path(output)/metadata['pcm_path']
    if metadata.get('pcm_encoding')=='hex_s16le_diagnostic':
        if metadata.get('source_kind')!='synthetic_cpu':
            raise ValueError('Encoded microphone fixture cannot claim original capture')
        return bytes.fromhex(source.read_text())
    if metadata.get('pcm_encoding') not in (None,'raw_s16le'):
        raise ValueError('Unknown microphone source encoding')
    return source.read_bytes()


def validate_source(output, expected_frames=600):
    output = Path(output)
    metadata_path=output/'pedestrian-microphone.json'
    if not metadata_path.is_file():
        raise ValueError('Original pedestrian microphone source missing')
    metadata = json.loads(metadata_path.read_text())
    raw = output / metadata['pcm_path']
    if metadata.get('source_kind') not in ('live_external_microphone','synthetic_cpu') or not raw.is_file():
        raise ValueError('Original pedestrian microphone source missing')
    if metadata.get('sample_rate_hz') != RATE or metadata.get('channels') != CHANNELS:
        raise ValueError('Pedestrian microphone format changed')
    pcm=load_pcm(output,metadata)
    if hashlib.sha256(pcm).hexdigest() != metadata.get('pcm_sha256'):
        raise ValueError('Original microphone bytes changed')
    if len(pcm) != metadata.get('pcm_bytes') or len(pcm) % BYTES_PER_SAMPLE:
        raise ValueError('Original microphone sample count differs')
    rows = [json.loads(line) for line in (output / 'pedestrian-microphone-frames.jsonl').read_text().splitlines()]
    if len(rows) != expected_frames or [r['video_frame'] for r in rows] != list(range(expected_frames)):
        raise ValueError('Original microphone frame map incomplete')
    if any(r['monotonic_ns'] <= 0 or r['native_frame'] <= 0 for r in rows):
        raise ValueError('Original microphone clock/frame source missing')
    if any(b['monotonic_ns'] <= a['monotonic_ns'] for a, b in zip(rows, rows[1:])):
        raise ValueError('Original microphone frame clock is not increasing')
    if metadata['pcm_bytes'] == 0 or metadata.get('start_monotonic_ns', 0) >= rows[0]['monotonic_ns']:
        raise ValueError('Microphone did not record before Native frames')
    if not metadata['start_monotonic_ns'] < metadata.get('first_chunk_monotonic_ns', 0) < rows[0]['monotonic_ns']:
        raise ValueError('Original microphone first-sample clock missing')
    if metadata.get('device_placement_verified') is not False:
        raise ValueError('Microphone placement needs independent source review')
    return {'pcm_sha256': metadata['pcm_sha256'], 'pcm_bytes': metadata['pcm_bytes'],
            'frames': len(rows), 'sample_rate_hz': RATE, 'original_audibility_verified': False}


class LiveMicrophone:
    """Record real ALSA PCM through ffmpeg while Native frames are captured."""

    def __init__(self, output, device, participant_id):
        if not device or not participant_id:
            raise ValueError('Explicit microphone device and pedestrian identity required')
        self.output = Path(output)
        self.device = device
        self.participant_id = participant_id
        self.process = None
        self.thread = None
        self.error = None
        self.start_ns = None
        self.frames = []
        self.first_chunk_ns = None
        self.pcm = self.output / 'pedestrian-microphone.s16le'

    def start(self):
        if self.pcm.exists():
            raise ValueError('New original microphone output required')
        self.start_ns = time.monotonic_ns()
        self.process = subprocess.Popen([
            'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
            '-f', 'alsa', '-i', self.device, '-ac', '1', '-ar', str(RATE),
            '-f', 's16le', '-acodec', 'pcm_s16le', 'pipe:1'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        def copy_pcm():
            try:
                with self.pcm.open('xb') as target:
                    while True:
                        chunk = self.process.stdout.read(8192)
                        if not chunk:
                            break
                        if self.first_chunk_ns is None:
                            self.first_chunk_ns = time.monotonic_ns()
                        target.write(chunk)
            except Exception as exc:
                self.error = repr(exc)

        self.thread = threading.Thread(target=copy_pcm, daemon=True)
        self.thread.start()
        deadline = time.monotonic() + 10
        while self.first_chunk_ns is None and time.monotonic() < deadline:
            if self.process.poll() is not None or self.error:
                raise RuntimeError('Live microphone did not start')
            time.sleep(.01)
        if self.first_chunk_ns is None:
            raise RuntimeError('Live microphone supplied no original samples')
        return self

    def mark_frame(self, video_frame, native_frame):
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError('Original microphone acquisition stopped')
        self.frames.append({'video_frame': video_frame, 'native_frame': native_frame,
                            'monotonic_ns': time.monotonic_ns(),
                            'pedestrian_id': self.participant_id})

    def finish(self, expected_frames=600):
        if self.process is None:
            raise ValueError('Original microphone was not started')
        self.process.terminate()
        try:
            self.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.thread.join(timeout=20)
        if self.thread.is_alive() or self.error:
            raise RuntimeError('Original microphone copy failed: ' + str(self.error))
        if len(self.frames) != expected_frames:
            raise ValueError('Original microphone frame map incomplete')
        metadata = {'source_kind': 'live_external_microphone', 'device': self.device,
                    'pedestrian_id': self.participant_id, 'pcm_path': self.pcm.name,
                    'pcm_sha256': digest(self.pcm), 'pcm_bytes': self.pcm.stat().st_size,
                    'sample_rate_hz': RATE, 'channels': CHANNELS,
                    'start_monotonic_ns': self.start_ns,
                    'first_chunk_monotonic_ns': self.first_chunk_ns,
                    'device_placement_verified': False,
                    'audible_signal_verified': False}
        (self.output / 'pedestrian-microphone.json').write_text(json.dumps(metadata, indent=2) + '\n')
        (self.output / 'pedestrian-microphone-frames.jsonl').write_text(
            ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in self.frames))
        return validate_source(self.output, expected_frames)
