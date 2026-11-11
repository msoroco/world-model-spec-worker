"""Capture an independent pedestrian-listener microphone WAV during Native ticks."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time


class ListenerCaptureProcess:
    def __init__(self, wav_path, *, device, sample_rate_hz=16000):
        self.path = Path(wav_path)
        self.device = str(device)
        self.rate = int(sample_rate_hz)
        if not self.device or self.rate < 160 or self.rate % 20:
            raise ValueError('Listener microphone device and 20 Hz compatible PCM rate required')
        if self.path.exists():
            raise ValueError('Retain prior original listener WAV')
        self.process = None
        self.started_monotonic_s = None

    def start(self):
        if self.process is not None:
            raise ValueError('Listener capture already started')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                   '-f', 'alsa', '-i', self.device, '-ac', '1', '-ar', str(self.rate),
                   '-c:a', 'pcm_s16le', str(self.path)]
        self.started_monotonic_s = time.monotonic()
        self.process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return command

    def stop(self):
        if self.process is None:
            raise ValueError('Listener capture not started')
        process = self.process
        self.process = None
        process.send_signal(signal.SIGINT)
        _, stderr = process.communicate(timeout=20)
        if process.returncode not in (0, 255) or not self.path.is_file() or self.path.stat().st_size < 44:
            raise ValueError('Listener microphone capture failed: ' + stderr.decode(errors='replace')[-500:])
        return {'source': str(self.path), 'device': self.device,
                'sample_rate_hz': self.rate, 'started_monotonic_s': self.started_monotonic_s,
                'stopped_monotonic_s': time.monotonic(), 'ffmpeg_exit_code': process.returncode}


def require_microphone_device():
    device = os.environ.get('C111603_LISTENER_ALSA_DEVICE')
    if not device:
        raise ValueError('C111603_LISTENER_ALSA_DEVICE required for affected-pedestrian Native capture')
    return device
