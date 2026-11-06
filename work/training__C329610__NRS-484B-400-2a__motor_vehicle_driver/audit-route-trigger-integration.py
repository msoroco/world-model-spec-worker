"""Independent 480-row synthetic source joins for all three fallback triggers."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE/'native'))
from fallback_triggers import evaluate
from pixel_visibility import measure as measure_pixels


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def write_rows(path, values):
    path.write_text(''.join(json.dumps(value, sort_keys=True)+'\n' for value in values))


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        samples, geometry, route = (folder/name for name in
                                     ('native_samples.jsonl','road_geometry.json','route_audit.json'))
        pixels, mapping, video, review = (folder/name for name in
            ('pixel_audit.json','video_frames.jsonl','approach.mkv','pixel_review.jsonl'))
        rows = [{'native_center_xy_m': [-35+25*i/479, -1.75],
                 'native_frame': 100+i, 'time_s': (i+1)/20} for i in range(480)]
        frame_rows = [{'video_frame': i, 'native_frame': 100+i,
                       'time_s': (i+1)/20} for i in range(480)]
        write_rows(samples, rows)
        write_rows(mapping, frame_rows)
        video.write_bytes(b'synthetic camera source; no original pixels')
        write(geometry, {'native_map_sha256': 'a'*64})
        base = {'source_kind': 'native_map_readback', 'connected_lane_link': True,
                'full_body_destination_exit_observed_by_24s': True,
                'native_samples_sha256': sha(samples),
                'road_geometry_sha256': sha(geometry),
                'native_map_sha256': 'a'*64}
        write(route, base)
        def review_visibility(count):
            write_rows(review, [{'video_frame': i, 'native_frame': 100+i,
                                 'body_visible': True, 'centerline_visible': i < count}
                                for i in range(480)])
            write(pixels, measure_pixels(samples, mapping, video, review))
        review_visibility(456)
        def trigger():
            return evaluate(samples, geometry, route, pixels, -1.75)
        assert [trigger()[key] for key in ('fallback1','fallback2','fallback3')] == [False]*3
        write(route, {**base, 'connected_lane_link': False})
        assert trigger()['fallback1'] is True
        write(route, base)
        rows[200]['native_center_xy_m'][1] = -2.11
        write_rows(samples, rows)
        write(route, {**base, 'native_samples_sha256': sha(samples)})
        review_visibility(456)
        assert trigger()['fallback2'] is True
        rows[200]['native_center_xy_m'][1] = -1.75
        write_rows(samples, rows)
        write(route, base)
        review_visibility(455)
        assert trigger()['fallback3'] is True
        video.write_bytes(b'changed synthetic camera source')
        try:
            trigger()
        except ValueError as error:
            assert 'Pixel review source or count mismatch' in str(error)
        else:
            raise AssertionError('Changed camera source accepted')
        print(json.dumps({'passed': True, 'synthetic_rows': 480,
                          'baseline_and_three_independent_trigger_variants': True,
                          'changed_camera_source_rejected': True,
                          'scope': 'mock source-contract only; no CARLA or original pixels'}))


if __name__ == '__main__':
    main()
