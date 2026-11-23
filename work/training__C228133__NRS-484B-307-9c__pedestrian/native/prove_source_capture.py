"""CPU proof for Native row builders; fake actors are never physical evidence."""

import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

from road_entry_measure import measure
from source_capture import (VIEWS, frame_map_row, pedestrian_device_row,
                            pedestrian_row, signal_state_row)


HERE = Path(__file__).resolve().parent
OUTPUT = HERE.parent / 'source-capture-row-proof.json'


class Footprint:
    def get_world_vertices(self, transform):
        return [SimpleNamespace(x=x, y=y) for x, y in
                ((0, -.8), (1, -.8), (1, .2), (0, .2))]


class Walker:
    id = 7
    type_id = 'walker.pedestrian.synthetic'
    bounding_box = Footprint()

    def get_transform(self):
        return None


class Light:
    def __init__(self, actor_id, state):
        self.id, self.state = actor_id, state

    def get_state(self):
        return self.state


def rejected(call, expected):
    try:
        call()
    except ValueError as error:
        assert expected in str(error), str(error)
        return str(error)
    raise AssertionError('Invalid source was accepted')


def prove():
    walker = pedestrian_row(0, 100, 1.0, Walker(), 'at_or_above_y')
    images = {view: ('diagnostic-' + view).encode() for view in VIEWS}
    video = frame_map_row(0, 100, 1.0, images)
    signal = signal_state_row(0, 100, 1.0, Light(21, 'Red'), Light(22, 'Green'))
    device = pedestrian_device_row(0, 100, 1.0)
    assert walker['footprint_roadward_y_m'] == .2
    assert walker['source_kind'] == 'native_actor'
    assert video['source_rgb_sha256'] == {
        view: hashlib.sha256(images[view]).hexdigest() for view in VIEWS}
    assert signal['observed_red_actor_state'] == 'Red'
    assert signal['observed_arrow_actor_state'] == 'Green'
    assert not signal['green_turn_arrow'] and not signal['directional_arrow_pixels_verified']
    assert not device['permission_reviewed'] and not device['permits_proceed']
    errors = [
        rejected(lambda: frame_map_row(0, 100, 1.0, {view: images[view]
                 for view in VIEWS[:3]}), 'four Native camera images'),
        rejected(lambda: signal_state_row(0, 100, 1.0,
                 Light(21, 'Red'), Light(21, 'Green')), 'distinct'),
        rejected(lambda: pedestrian_row(0, 100, 1.0, Walker(), 'unknown'),
                 'calibrated road side'),
    ]
    repo = HERE.parents[2]
    ignored = repo / '.runtime-work'
    ignored.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ignored, prefix='c228133-capture-review-') as temp:
        folder = Path(temp)
        (folder / 'road-boundary.json').write_text(json.dumps({
            'format': 'pedestrian-road-boundary-v1', 'road_side': 'at_or_above_y',
            'boundary_y_m': 0, 'source_kind': 'native_map_readback'}) + '\n')
        for name, row in (('native-pedestrian-frames.jsonl', walker),
                          ('native-signal-frames.jsonl', signal),
                          ('native-pedestrian-device-frames.jsonl', device),
                          ('video_frames.jsonl', video)):
            (folder / name).write_text(json.dumps(row) + '\n')
        errors.append(rejected(lambda: measure(folder),
                               'signal pixel/governance review incomplete'))
    return {'format': 'c228133-source-capture-row-proof-v1', 'passed': True,
            'source_sha256': hashlib.sha256((HERE / 'source_capture.py').read_bytes()).hexdigest(),
            'source_kind': 'synthetic_cpu_actor_stubs',
            'camera_views': list(VIEWS), 'native_frame': video['native_frame'],
            'observed_footprint_roadward_y_m': walker['footprint_roadward_y_m'],
            'signal_claims_deferred': True, 'device_permission_deferred': True,
            'negative_errors': errors, 'original_native_observed': False,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    receipt = prove()
    OUTPUT.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))
