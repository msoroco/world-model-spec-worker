import json
from pathlib import Path
import socket
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from turn_horn_relay import HornRelay


class HornRelayTests(unittest.TestCase):
    def test_matches_ack_to_native_frame_and_actor(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server.bind(('127.0.0.1', 0))
        port = server.getsockname()[1]

        def respond():
            data, client = server.recvfrom(4096)
            request = json.loads(data)
            server.sendto(json.dumps({'kind': 'horn_ack', 'nonce': request['nonce'],
                'frame': request['frame'], 'vehicle_actor_id': request['vehicle_actor_id']}).encode(), client)
            server.close()

        thread = threading.Thread(target=respond, daemon=True)
        thread.start()
        receipt = HornRelay('127.0.0.1', port).request(frame=42, time_s=.45, vehicle_actor_id=7)
        thread.join(timeout=2)
        self.assertEqual(receipt['request']['frame'], 42)
        self.assertFalse(receipt['physical_sound_verified'])

    def test_rejects_missing_ack(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server.bind(('127.0.0.1', 0))
        port = server.getsockname()[1]
        try:
            with self.assertRaisesRegex(ValueError, 'acknowledgement missing'):
                HornRelay('127.0.0.1', port, timeout_s=.01).request(frame=42, time_s=.45,
                                                                   vehicle_actor_id=7)
        finally:
            server.close()


if __name__ == '__main__':
    unittest.main()
