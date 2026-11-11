"""Request a physical horn relay event and retain its acknowledgement only."""
import json
import os
import secrets
import socket
import time


def relay_endpoint_from_env():
    host = os.environ.get('C111603_HORN_RELAY_HOST')
    port = os.environ.get('C111603_HORN_RELAY_PORT')
    if not host or not port:
        raise ValueError('C111603_HORN_RELAY_HOST and PORT required for Native horn capture')
    port = int(port)
    if port <= 0 or port > 65535:
        raise ValueError('Horn relay port out of range')
    return host, port


class HornRelay:
    def __init__(self, host, port, *, timeout_s=1.0):
        self.host, self.port = str(host), int(port)
        self.timeout_s = float(timeout_s)
        if not self.host or not 0 < self.port <= 65535 or self.timeout_s <= 0:
            raise ValueError('Horn relay endpoint or timeout invalid')

    def request(self, *, frame, time_s, vehicle_actor_id):
        if type(frame) is not int or frame < 0 or type(vehicle_actor_id) is not int:
            raise ValueError('Horn relay needs original frame and Native actor identity')
        nonce = secrets.token_hex(16)
        request = {'kind': 'horn_on', 'nonce': nonce, 'frame': frame,
                   'native_time_s': float(time_s), 'vehicle_actor_id': vehicle_actor_id}
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(self.timeout_s)
            client.sendto(json.dumps(request).encode(), (self.host, self.port))
            try:
                raw, address = client.recvfrom(4096)
            except socket.timeout as error:
                raise ValueError('Horn relay acknowledgement missing') from error
        try:
            response = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError('Horn relay acknowledgement invalid') from error
        if (response.get('kind') != 'horn_ack' or response.get('nonce') != nonce or
                response.get('frame') != frame or response.get('vehicle_actor_id') != vehicle_actor_id):
            raise ValueError('Horn relay acknowledgement does not match request')
        return {'request': request, 'acknowledgement': response,
                'remote_address': [address[0], address[1]],
                'ack_received_monotonic_s': time.monotonic(),
                'physical_sound_verified': False}
