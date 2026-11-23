"""CPU checks for the 30-second controller and original saved-source boundary."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from prepare_pass import prepare
from runner import CAMERA_SPECS, check, lookahead_index

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def reject(raw, review, output, config, expected):
    try:
        prepare(raw, review, output, config)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(f'Wrong rejection: {error}') from error
        return str(error)
    raise AssertionError('Invalid original source accepted')


def prove():
    positives = []
    for distance in (70, 120, 170):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            bundle = HERE/'drafts'/str(distance)/candidate
            result = check(bundle, distance, candidate)
            assert result['requested_frames'] == 600
            positives.append({'distance_m': distance, 'candidate_id': candidate,
                              'config_sha256': sha(bundle/'config.json')})
    assert tuple(name for name, *_ in CAMERA_SPECS) == (
        'overview', 'approach', 'reference_corner', 'driver_reference')
    assert [lookahead_index(i, 600) for i in (0, 479, 480, 590, 599)] == [
        15, 494, 495, 599, 599]
    with tempfile.TemporaryDirectory(dir=HERE.parents[2]/'.runtime-work') as temporary:
        root = Path(temporary)
        raw = root/'raw'
        shutil.copytree(HERE/'raw-fixtures'/'120', raw)
        actors = raw/'native-raw-actors.jsonl'
        rows = [json.loads(line) for line in actors.read_text().splitlines()]
        for row in rows:
            row['source_kind'] = 'original_native'
        actors.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows))
        review_path = raw/'sightline-review.json'
        review = json.loads(review_path.read_text())
        review['source_kind'] = 'original_native'
        review['review_provenance'] = 'human_frame_review'
        (raw/'forward-video-stub.txt').unlink()
        for name, *_ in CAMERA_SPECS:
            (raw/(name+'.mkv')).write_bytes(b'invalid diagnostic media '+name.encode())
        review['source_hashes'] = {name: sha(raw/name) for name in (
            'native-raw-actors.jsonl', 'native-map-readback.json', 'video_frames.jsonl')}
        review['source_hashes'].update({name+'_video': sha(raw/(name+'.mkv'))
                                        for name, *_ in CAMERA_SPECS})
        config = HERE/'drafts/120/primary/config.json'
        missing = reject(raw, review_path, root/'missing', config, 'source absent')
        (raw/'raw.mkv').write_bytes(b'invalid diagnostic primary media')
        review['source_hashes']['primary_video'] = sha(raw/'raw.mkv')
        write_json(review_path, review)
        invalid = reject(raw, review_path, root/'invalid', config,
                         'Original FFV1 camera could not be verified')
        (raw/'overview.mkv').write_bytes(b'changed diagnostic media')
        stale = reject(raw, review_path, root/'stale', config,
                       'Sightline review source binding')
    proof = {'format': 'c102951-capture-source-path-cpu-proof-v1',
             'assignment_id': HERE.parent.name,
             'runner_sha256': sha(HERE/'runner.py'),
             'preparer_sha256': sha(HERE/'prepare_pass.py'),
             'positive_request_bundles': positives,
             'camera_names': [name for name, *_ in CAMERA_SPECS],
             'lookahead_indices': {'0': 15, '479': 494, '480': 495,
                                   '590': 599, '599': 599},
             'negative_missing_composite': missing,
             'negative_invalid_media': invalid,
             'negative_stale_review_hash': stale,
             'original_native_observed': False, 'delivery_ready': False}
    write_json(HERE/'capture-path-proof.json', proof)
    return proof


if __name__ == '__main__':
    result = prove()
    print(json.dumps({'request_positives': len(result['positive_request_bundles']),
                      'source_rejections': 3,
                      'last_lookahead': result['lookahead_indices']['599']}))
