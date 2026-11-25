"""Synthetic-only Native construction protocol probe for one exact case."""
import argparse
import hashlib
import json
from pathlib import Path

from native_overtake import build, request_signal


class FixtureAdapter:
    def __init__(self):
        self.calls = []

    def map_opendrive_bytes(self):
        return b'<OpenDRIVE synthetic sidewalk fixture/>'

    def sidewalk_route_readback(self, route, sidewalk_id):
        self.calls.append(('route', sidewalk_id, len(route)))
        return sidewalk_id == 'SYNTHETIC_SIDEWALK'

    def spawn_rider(self, kind, point, **kwargs):
        self.calls.append(('rider', kind, point))
        return 'synthetic_rider'

    def spawn_pedestrian(self, point, **kwargs):
        self.calls.append(('pedestrian', point))
        return 'synthetic_pedestrian'

    def attach_audible_emitter(self, rider, **kwargs):
        self.calls.append(('emitter', rider))
        return 'synthetic_emitter'

    def read_emitter(self, emitter):
        return {'physically_present': True}

    def attach_pedestrian_microphone(self, pedestrian, **kwargs):
        self.calls.append(('microphone', pedestrian))
        return 'synthetic_microphone'

    def read_microphone(self, microphone):
        return {'recording_enabled': True}

    def set_rider_route(self, rider, route):
        self.calls.append(('rider_route', len(route)))

    def set_pedestrian_route(self, pedestrian, route):
        self.calls.append(('pedestrian_route', len(route)))

    def emit_audible_signal(self, emitter):
        self.calls.append(('emit', emitter))

    def destroy(self, resource):
        self.calls.append(('destroy', resource))


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / 'config.json').read_text())
    site = json.loads((root / 'scene.json').read_text())
    if (site.get('source_kind') != 'synthetic_diagnostic_fixture' or
            config['selected_case_id'] != site['case_id'] or
            config['rate_hz'] != 20 or config['duration_s'] != 45 or
            config['case']['rider_kind'] != site['rider_kind']):
        raise ValueError('exact synthetic sidewalk construction changed')
    expected = hashlib.sha256(b'<OpenDRIVE synthetic sidewalk fixture/>').hexdigest()
    if site['map_sha256'] != expected:
        raise ValueError('synthetic map binding changed')
    adapter = FixtureAdapter()
    built = build(adapter, site)
    if len(built['owned']) != 4 or adapter.calls.count(('route', 'SYNTHETIC_SIDEWALK', 2)) != 2:
        raise ValueError('synthetic rider/pedestrian/audio construction incomplete')
    signal = config['case']['signal_frame']
    if signal is not None:
        if not request_signal(adapter, built['emitter'], signal, signal):
            raise ValueError('synthetic signal schedule missed')
    if bool(signal is not None) != any(call[0] == 'emit' for call in adapter.calls):
        raise ValueError('synthetic signal output changed')
    return site


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    scene = check()
    if not args.check:
        raise ValueError('Synthetic sidewalk source cannot authorize Native capture')
    print('synthetic construction protocol passed: ' + scene['case_id'])
