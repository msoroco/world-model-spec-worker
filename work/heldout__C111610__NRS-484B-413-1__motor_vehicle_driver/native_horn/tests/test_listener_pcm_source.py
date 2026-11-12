from pathlib import Path
import struct
import sys
import tempfile
import unittest
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from listener_pcm_source import ListenerPcmSource


class ListenerPcmSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'listener.wav'
        with wave.open(str(self.path), 'wb') as sink:
            sink.setnchannels(1)
            sink.setsampwidth(2)
            sink.setframerate(160)
            sink.writeframes(struct.pack('<' + 'h' * 24, *([0] * 8 + [8192] * 8 + [0] * 8)))

    def test_reads_original_pcm_windows_at_native_frames(self):
        source = ListenerPcmSource(self.path, 'ped_1', first_frame=40,
                                   source_start_time_s=0, capture_provenance='listener recorder take 1')
        packets = [source.packet(40 + i, i / 20) for i in range(3)]
        source.close()
        self.assertEqual(packets[1]['samples'], [.25] * 8)
        self.assertEqual(packets[1]['origin'], 'listener_pcm_capture')
        self.assertEqual(len(packets[1]['capture_source_sha256']), 64)

    def test_rejects_unsynchronized_or_short_pcm(self):
        source = ListenerPcmSource(self.path, 'ped_1', first_frame=40,
                                   source_start_time_s=0, capture_provenance='listener recorder take 1')
        with self.assertRaisesRegex(ValueError, 'times differ'):
            source.packet(40, .1)
        source.packet(40, 0)
        with self.assertRaisesRegex(ValueError, 'skipped'):
            source.packet(42, .1)
        source.packet(41, .05)
        source.packet(42, .1)
        with self.assertRaisesRegex(ValueError, 'ended before'):
            source.packet(43, .15)
        source.close()


if __name__ == '__main__':
    unittest.main()
