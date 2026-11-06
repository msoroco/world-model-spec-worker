"""Independent synthetic source-join audit for the proposed Native fallback path."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from fallback_triggers import evaluate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        samples = folder / 'native_samples.jsonl'
        geometry = folder / 'road_geometry.json'
        route = folder / 'route_audit.json'
        pixels = folder / 'pixel_audit.json'
        rows = [{'native_center_xy_m': [-35 + 25*i/479, 1.75],
                 'native_frame': i, 'time_s': (i+1)/20} for i in range(480)]
        samples.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows))
        write(geometry, {'native_map_sha256': 'a'*64})
        base = {'source_kind': 'native_map_readback', 'connected_lane_link': True,
                'full_body_destination_exit_observed_by_24s': True,
                'native_samples_sha256': sha(samples),
                'road_geometry_sha256': sha(geometry),
                'native_map_sha256': 'a'*64}
        write(route, base)
        write(pixels, {'source_kind': 'original_camera_pixels',
                       'body_and_centerline_visible_frames': 95,
                       'approach_frames': 100})
        def trigger():
            return evaluate(samples, geometry, route, pixels, 1.75)
        assert [trigger()[key] for key in ('fallback1','fallback2','fallback3')] == [False]*3
        write(route, {**base, 'connected_lane_link': False})
        assert trigger()['fallback1'] is True
        write(route, base)
        rows[200]['native_center_xy_m'][1] = 2.11
        samples.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows))
        write(route, {**base, 'native_samples_sha256': sha(samples)})
        assert trigger()['fallback2'] is True
        rows[200]['native_center_xy_m'][1] = 1.75
        samples.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows))
        write(route, base)
        write(pixels, {'source_kind': 'original_camera_pixels',
                       'body_and_centerline_visible_frames': 94,
                       'approach_frames': 100})
        assert trigger()['fallback3'] is True
        rows[200]['native_center_xy_m'][1] = 2.11
        samples.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows))
        try:
            trigger()
        except ValueError as error:
            assert 'source hash mismatch' in str(error)
        else:
            raise AssertionError('Changed Native samples accepted')
        print(json.dumps({'passed': True, 'synthetic_rows': 480,
                          'baseline_and_three_independent_trigger_variants': True,
                          'changed_native_samples_rejected': True,
                          'scope': 'mock source-contract only; no CARLA or original pixels'}))


if __name__ == '__main__':
    main()
