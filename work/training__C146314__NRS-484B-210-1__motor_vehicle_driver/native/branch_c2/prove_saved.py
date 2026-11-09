"""Exercise copied c2 raw preparation and reject changed evidence."""
import json
from pathlib import Path
import shutil
import tempfile

from saved import measure, prepare
from route_fallbacks import route

HERE = Path(__file__).resolve().parent


def mutate_json(path, key, value):
    data = json.loads(path.read_text())
    data[key] = value
    path.write_text(json.dumps(data)+'\n')


def mutate_row(path, key, value):
    lines = path.read_text().splitlines()
    row = json.loads(lines[100])
    row[key] = value
    lines[100] = json.dumps(row)
    path.write_text('\n'.join(lines)+'\n')


def invert_survey(path):
    data = json.loads(path.read_text())
    survey = data['private_way_full_window_survey']
    if any(point['road_id'] == 214 for point in survey):
        for point in survey:
            point['road_id'] = None
    else:
        survey[80]['road_id'] = 214
    path.write_text(json.dumps(data)+'\n')


def rejected(bundle, raw, change):
    with tempfile.TemporaryDirectory(prefix='c2-negative-') as tmp:
        target = Path(tmp)/'raw'
        shutil.copytree(raw, target)
        change(target)
        try:
            prepare(bundle, target, Path(tmp)/'saved', synthetic=True)
        except (ValueError, KeyError, TypeError, FileNotFoundError):
            return True
        return False


def missing_original_media_rejected(bundle, raw):
    with tempfile.TemporaryDirectory(prefix='c2-original-negative-') as tmp:
        target = Path(tmp)/'raw'
        shutil.copytree(raw, target)
        mutate_json(target/'native-map-readback.json', 'source_kind', 'original_native')
        for name in ('native-raw-actors.jsonl', 'frame-review.jsonl'):
            path = target/name
            data = [json.loads(line) for line in path.read_text().splitlines()]
            for row in data:
                row['source_kind'] = 'original_native'
                if name == 'frame-review.jsonl':
                    row['review_provenance'] = 'human_frame_review'
            path.write_text(''.join(json.dumps(row)+'\n' for row in data))
        try:
            prepare(bundle, target, Path(tmp)/'saved', synthetic=False)
        except FileNotFoundError:
            return True
        return False


def prove():
    manifest = json.loads((HERE/'offline/manifest.json').read_text())
    positives = negatives = 0
    for entry in manifest['entries']:
        bundle = HERE/entry['bundle']
        raw = HERE/'offline/raw-fixtures'/bundle.parent.name/bundle.name
        saved = HERE/'offline/saved-fixtures'/bundle.parent.name/bundle.name
        m = measure(bundle, saved)
        r = route(bundle, saved)
        if m['source_kind'] != 'synthetic_cpu' or m['delivery_ready'] or \
           r['selected_fallback'] is not None or \
           m['private_way_requested'] != (bundle.parent.name == 'exception_3_1'):
            raise ValueError('synthetic positive')
        positives += 1
        changes = (
            lambda d: mutate_json(d/'native-map-readback.json', 'private_way_verified', not m['private_way_requested']),
            lambda d: mutate_json(d/'native-capture-report.json', 'config_sha256', '0'*64),
            lambda d: mutate_row(d/'native-raw-actors.jsonl', 'native_frame', -1),
            lambda d: mutate_row(d/'native-raw-actors.jsonl', 'private_way_verified', None),
            lambda d: mutate_row(d/'video_frames.jsonl', 'native_frame', -1),
            lambda d: mutate_row(d/'frame-review.jsonl', 'review_provenance', 'claimed_human'),
            lambda d: mutate_row(d/'frame-review.jsonl', 'private_way_pixel_reviewed', 'yes'),
            lambda d: mutate_json(d/'native-map-readback.json', 'road_sha256', '0'*64),
            lambda d: mutate_json(d/'native-map-readback.json',
                                  'generated_junction_connection_verified', None),
            lambda d: mutate_json(d/'native-map-readback.json',
                                  'private_way_full_window_survey', []),
            lambda d: invert_survey(d/'native-map-readback.json'),
        )
        for change in changes:
            if not rejected(bundle, raw, change):
                raise ValueError('tamper accepted '+str(change))
            negatives += 1
        if not missing_original_media_rejected(bundle, raw):
            raise ValueError('missing original FFV1 accepted')
        negatives += 1
    output = {'format': 'c146314-paragraph-c2-saved-compatibility-v1',
              'positive': positives, 'tamper_negative': negatives,
              'original_native_observed': False, 'delivery_ready': False}
    (HERE/'offline/saved-compatibility.json').write_text(json.dumps(output, indent=2)+'\n')
    return output


if __name__ == '__main__':
    print(json.dumps(prove()))
