"""Exercise request pair identity, provenance and fixed pedestrian conditions."""

import json
import shutil
import tempfile
from pathlib import Path

from build_requests import AID, ROOT, sha
from check_requests import check_pair


def reject(root, expected):
    try:
        check_pair(root)
    except ValueError as exc:
        if expected not in str(exc):
            raise AssertionError(str(exc)) from exc
        return str(exc)
    raise AssertionError('Changed request pair was accepted')


def main():
    positive = check_pair()
    negatives = []
    with tempfile.TemporaryDirectory(prefix='c213851-requests-') as tmp:
        root = Path(tmp)
        for suffix in ('stop_before_sidewalk', 'cross_without_stop'):
            shutil.copytree(ROOT / 'native' / suffix, root / 'native' / suffix)
        track = root / 'native/cross_without_stop/requested-tracks.jsonl'
        data = track.read_text()
        track.write_text(data.replace('"requested_pedestrian_cross_track_m": 1.0',
                                      '"requested_pedestrian_cross_track_m": 2.0', 1))
        negatives.append(reject(root, 'request differs'))
        track.write_text(data)
        config_path = root / 'native/cross_without_stop/config.json'
        config = json.loads(config_path.read_text())
        config['source_review_required'] = []
        config_path.write_text(json.dumps(config, indent=2) + '\n')
        negatives.append(reject(root, 'construction context differs'))
    proof = {'format': 'road-to-driveway-request-proof', 'passed': True,
             'positive': positive, 'negative_count': len(negatives),
             'negative_errors': negatives, 'actual_native_motion_observed': False}
    path = ROOT / 'native/request-proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed': True, 'negative_count': len(negatives),
                      'proof_sha256': sha(path)}))


if __name__ == '__main__':
    main()
