"""Read source PCM at an identified listener, joined to 20 Hz Native frames.

The WAV must be an independently captured source. This reader never generates
horn sound from a controller command or labels it legally audible.
"""
from hashlib import sha256
from math import isfinite
from pathlib import Path
import struct
import wave


class ListenerPcmSource:
    def __init__(self, wav_path, listener_id, *, first_frame, source_start_time_s,
                 capture_provenance):
        self.path = Path(wav_path)
        if not self.path.is_file() or not capture_provenance:
            raise ValueError('Original listener WAV and capture provenance required')
        self.listener_id = str(listener_id)
        if not self.listener_id or type(first_frame) is not int:
            raise ValueError('Listener identity and Native first frame required')
        self.first_frame = first_frame
        self.start_time = float(source_start_time_s)
        if not isfinite(self.start_time):
            raise ValueError('Listener source start time is nonfinite')
        self.provenance = capture_provenance
        self.digest = sha256(self.path.read_bytes()).hexdigest()
        self.wav = wave.open(str(self.path), 'rb')
        if (self.wav.getnchannels(), self.wav.getsampwidth()) != (1, 2):
            self.wav.close()
            raise ValueError('Listener source must be mono signed 16-bit PCM')
        self.rate = self.wav.getframerate()
        if self.rate % 20 or self.rate < 160:
            self.wav.close()
            raise ValueError('Listener PCM rate cannot join exact 20 Hz frames')
        self.samples_per_frame = self.rate // 20
        self.previous = None

    def packet(self, frame, time_s):
        if type(frame) is not int or frame < self.first_frame:
            raise ValueError('Listener packet frame precedes source start')
        expected_time = self.start_time + (frame - self.first_frame) / 20
        time_s = float(time_s)
        if not isfinite(time_s) or abs(time_s - expected_time) > 1e-4:
            raise ValueError('Listener PCM and Native frame times differ')
        if self.previous is not None and frame != self.previous + 1:
            raise ValueError('Listener PCM skipped a Native frame')
        index = (frame - self.first_frame) * self.samples_per_frame
        if self.wav.tell() != index:
            self.wav.setpos(index)
        raw = self.wav.readframes(self.samples_per_frame)
        if len(raw) != self.samples_per_frame * 2:
            raise ValueError('Original listener WAV ended before Native frame')
        samples = [sample / 32768 for sample in struct.unpack('<' + 'h' * self.samples_per_frame, raw)]
        self.previous = frame
        return {'origin': 'listener_pcm_capture', 'frame': frame,
                'listener_id': self.listener_id, 'capture_source': str(self.path),
                'capture_source_sha256': self.digest,
                'capture_provenance': self.provenance, 'sample_rate_hz': self.rate,
                'samples': samples}

    def close(self):
        self.wav.close()
