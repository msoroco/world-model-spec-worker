import json
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from turn_horn_relay import HornRelay


class FakeSocket:
    def __init__(self, *, timeout=False):
        self.timeout = timeout
        self.request = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def settimeout(self, value):
        self.timeout_s = value

    def sendto(self, data, endpoint):
        self.request = json.loads(data)
        self.endpoint = endpoint

    def recvfrom(self, size):
        if self.timeout:
            raise socket.timeout()
        request = self.request
        return json.dumps({'kind': 'horn_ack', 'nonce': request['nonce'],
            'frame': request['frame'], 'vehicle_actor_id': request['vehicle_actor_id']}).encode(), self.endpoint


class HornRelayTests(unittest.TestCase):
    def test_matches_ack_to_native_frame_and_actor(self):
        fake = FakeSocket()
        with patch('turn_horn_relay.socket.socket', return_value=fake):
            receipt = HornRelay('127.0.0.1', 9999).request(frame=42, time_s=.45,
                                                            vehicle_actor_id=7)
        self.assertEqual(receipt['request']['frame'], 42)
        self.assertEqual(fake.endpoint, ('127.0.0.1', 9999))
        self.assertFalse(receipt['physical_sound_verified'])

    def test_rejects_missing_ack(self):
        with patch('turn_horn_relay.socket.socket', return_value=FakeSocket(timeout=True)):
            with self.assertRaisesRegex(ValueError, 'acknowledgement missing'):
                HornRelay('127.0.0.1', 9999, timeout_s=.01).request(frame=42, time_s=.45,
                                                                    vehicle_actor_id=7)


if __name__ == '__main__':
    unittest.main()
