"""Copied raw-to-saved positives, tamper negatives and measured trigger probes."""
import json
from pathlib import Path
import shutil
import tempfile

from saved import measure, prepare
from route_fallbacks import route

HERE = Path(__file__).resolve().parent


def edit(path, key, value):
    data = json.loads(path.read_text())
    data[key] = value
    path.write_text(json.dumps(data) + '\n')


def edit_row(path, key, value, index=100):
    data = [json.loads(line) for line in path.read_text().splitlines()]
    data[index][key] = value
    path.write_text(''.join(json.dumps(row) + '\n' for row in data))


def edit_ego(path, field, value, index=100):
    data = [json.loads(line) for line in path.read_text().splitlines()]
    data[index]['ego'][field] = value
    path.write_text(''.join(json.dumps(row) + '\n' for row in data))


def original_without_media(raw):
    edit(raw / 'native-map-readback.json', 'source_kind', 'original_native')
    for name in ('native-raw-actors.jsonl', 'frame-review.jsonl'):
        path = raw / name
        data = [json.loads(line) for line in path.read_text().splitlines()]
        for row in data:
            row['source_kind'] = 'original_native'
            if name == 'frame-review.jsonl':
                row['review_provenance'] = 'human_frame_review'
        path.write_text(''.join(json.dumps(row) + '\n' for row in data))


def weaken_observed_stop(raw):
    path = raw / 'native-raw-actors.jsonl'
    data = [json.loads(line) for line in path.read_text().splitlines()]
    if data[100]['requested_speed_mps'] != 0:
        raise ValueError('expected held stop frame')
    data[100]['ego']['speed_mps'] = .2
    data[100]['ego']['velocity_native_xyz_mps'] = [.2, 0, 0]
    path.write_text(''.join(json.dumps(row) + '\n' for row in data))


def rejected(bundle, raw, change, original=False):
    with tempfile.TemporaryDirectory(prefix='c10389-saved-negative-') as folder:
        target = Path(folder) / 'raw'
        shutil.copytree(raw, target)
        change(target)
        try:
            prepare(bundle, target, Path(folder) / 'saved', synthetic=not original)
        except (ValueError, KeyError, TypeError, FileNotFoundError):
            return True
        return False


def prove():
    copied = json.loads((HERE / 'offline' / 'manifest.json').read_text())
    positives = negatives = trigger_positives = 0
    for entry in copied['entries']:
        bundle = HERE / entry['bundle']
        suffix = bundle.parent.name
        candidate = bundle.name
        raw = HERE / 'offline' / 'raw-fixtures' / suffix / candidate
        saved = HERE / 'offline' / 'saved-fixtures' / suffix / candidate
        measured = measure(bundle, saved)
        routed = route(bundle, saved)
        if (measured['source_kind'] != 'synthetic_cpu' or
                measured['delivery_ready'] or
                measured['authored_signal_is_official_placement'] or
                routed['selected_fallback'] is not None):
            raise ValueError('synthetic saved positive promoted')
        positives += 1
        changes = (
            lambda d: edit(d / 'native-map-readback.json', 'road_sha256', '0'*64),
            lambda d: edit(d / 'native-map-readback.json', 'lane_readback', {}),
            lambda d: edit(d / 'native-map-readback.json', 'stop_landmark_readback', {}),
            lambda d: edit(d / 'native-map-readback.json', 'official_placement_verified', True),
            lambda d: edit(d / 'native-capture-report.json', 'config_sha256', '0'*64),
            lambda d: edit_row(d / 'native-raw-actors.jsonl', 'observed_lane_id', 0),
            lambda d: edit_row(d / 'video_frames.jsonl', 'native_frame', -1),
            lambda d: edit_row(d / 'frame-review.jsonl', 'review_provenance', 'claimed_human'),
            lambda d: edit_row(d / 'frame-review.jsonl', 'device_face_pixel_reviewed', 'yes'),
            lambda d: edit_ego(d / 'native-raw-actors.jsonl', 'speed_mps', 99),
        )
        for change in changes:
            if not rejected(bundle, raw, change):
                raise ValueError('tampered raw accepted')
            negatives += 1
        if not rejected(bundle, raw, original_without_media, original=True):
            raise ValueError('missing original FFV1 media accepted')
        negatives += 1
        if suffix == 'probe_1' and candidate == 'primary':
            with tempfile.TemporaryDirectory(prefix='c10389-trigger-') as folder:
                target = Path(folder) / 'raw'
                shutil.copytree(raw, target)
                reviews = [json.loads(line) for line in
                           (target / 'frame-review.jsonl').read_text().splitlines()]
                for row in reviews:
                    row['device_face_pixel_reviewed'] = False
                    row['device_face_visible'] = None
                (target / 'frame-review.jsonl').write_text(''.join(
                    json.dumps(row) + '\n' for row in reviews))
                fresh = Path(folder) / 'saved'
                prepare(bundle, target, fresh, synthetic=True)
                if not route(bundle, fresh)['triggers']['fallback2']['eligible']:
                    raise ValueError('missing visual review trigger absent')
                trigger_positives += 1
            with tempfile.TemporaryDirectory(prefix='c10389-stop-trigger-') as folder:
                target = Path(folder) / 'raw'
                shutil.copytree(raw, target)
                weaken_observed_stop(target)
                fresh = Path(folder) / 'saved'
                prepare(bundle, target, fresh, synthetic=True)
                if (measure(bundle, fresh)['stopped_before_device_frames'] != 19 or
                        not route(bundle, fresh)['triggers']['fallback1']['eligible']):
                    raise ValueError('weakened measured stop trigger absent')
                trigger_positives += 1
    result = {'format': 'c10389-device-saved-compatibility-v1',
              'positive': positives, 'tamper_negative': negatives,
              'measured_trigger_positive': trigger_positives,
              'original_native_observed': False, 'delivery_ready': False}
    (HERE / 'offline' / 'saved-compatibility.json').write_text(
        json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    print(json.dumps(prove()))
