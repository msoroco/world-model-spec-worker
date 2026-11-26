"""CPU source-join proof for prospective saved analysis."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from build_saved_packet import build
from prove_designated_stop import packet
from saved_measure import process


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_attempt(folder, inside):
    folder.mkdir()
    source = packet(folder / 'originals', inside)
    case = ('training__C229954__NRS-484B-500__vehicle_stopping_person__'
            'selected_d67fe2ae__condition_' + ('a' if inside else 'b'))
    (folder / 'config.json').write_text(json.dumps({
        'case_id': case, 'activity_mode': 'stop'}) + '\n')
    copies = {}
    for name in ('device', 'designation', 'map'):
        target = folder / ('original-' + name + '.json')
        shutil.copyfile(source['sources'][name]['path'], target)
        copies[name] = {'path': str(target), 'sha256': sha(target)}
    route = folder / 'original-route.json'
    route.write_text(json.dumps({'source_kind': 'synthetic_route_for_cpu_test'}) + '\n')
    copies['route'] = {'path': str(route), 'sha256': sha(route)}
    review = {'source_kind': 'original_official_device_review',
              'map_name': 'synthetic-map', 'device_id': 'synthetic-device-1',
              'sources': copies}
    (folder / 'original-review.json').write_text(json.dumps(review) + '\n')
    for name, target in (('person_activity', 'person-activity.json'),
                         ('traffic_direction', 'traffic-direction.json')):
        shutil.copyfile(source['sources'][name]['path'], folder / target)
    for name, target in (('native_trace', 'native-stop-trace.jsonl'),
                         ('video_frame_map', 'video_frames.jsonl')):
        rows = json.loads(Path(source['sources'][name]['path']).read_text())
        (folder / target).write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
    return folder


def reject(folder, source_name, expected):
    path = folder / source_name
    original = path.read_bytes()
    path.unlink()
    try:
        build(folder)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError((expected, str(error))) from error
        return str(error)
    finally:
        path.write_bytes(original)
    raise AssertionError('Missing saved source accepted: ' + source_name)


def main():
    with tempfile.TemporaryDirectory(prefix='c229954-saved-', dir='.runtime-work') as temporary:
        base = Path(temporary)
        a = make_attempt(base / 'a', True)
        b = make_attempt(base / 'b', False)
        inside, outside = build(a), build(b)
        assert inside['rest_and_body_overlap_frames'] == 500
        assert outside['rest_and_body_overlap_frames'] == 0
        before = {str(path.relative_to(a)): sha(path) for path in a.rglob('*')
                  if path.is_file()}
        saved = process(a, base / 'saved-analysis.json')
        assert saved['measurement']['rest_and_body_overlap_frames'] == 500
        assert saved['original_source_hashes'] == before
        assert before == {str(path.relative_to(a)): sha(path) for path in a.rglob('*')
                          if path.is_file()}
        try:
            process(a, a / 'forbidden-analysis.json')
        except ValueError as error:
            assert 'must not rewrite original acquisition' in str(error)
        else:
            raise AssertionError('Saved analysis wrote into original attempt')
        negatives = {
            name: reject(a, name, 'Missing required source: ' + name)
            for name in ('person-activity.json', 'traffic-direction.json',
                         'original-designation.json', 'native-stop-trace.jsonl',
                         'video_frames.jsonl')
        }
        print(json.dumps({'format': 'worker-designated-stop-saved-packet-cpu-proof',
                          'inside': inside, 'outside': outside,
                          'negative_rejections': negatives,
                          'saved_output_outside_original': True,
                          'synthetic_only': True, 'physical_completion': False},
                         indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
