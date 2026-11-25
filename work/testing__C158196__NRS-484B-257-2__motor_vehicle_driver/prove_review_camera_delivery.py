"""Audit every selected saved camera-review record and reject changed sources."""

import hashlib
import json
import os
from pathlib import Path
import tempfile

from review_camera_delivery import audit


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    private = (REPO / '.runtime-work').resolve()
    if output != private and private not in output.parents:
        raise ValueError('Output root outside .runtime-work')
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    receipts = []
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        attempt = REPO / '.runtime-work/c158196-review-compat-all-r2' / (suffix + '-primary')
        positive = audit(attempt)
        with tempfile.TemporaryDirectory(dir=output) as temporary:
            target = Path(temporary)
            (target / 'channels').mkdir()
            for name in ('video_frames.jsonl', *(camera + '.mkv' for camera in CAMERAS)):
                os.link(attempt / name, target / name)
            source = attempt / 'channels/original_camera_review.json'
            record = json.loads(source.read_text())
            record['original_camera_review']['source_sha256']['overview.mkv'] = '0' * 64
            (target / 'channels/original_camera_review.json').write_text(json.dumps(record) + '\n')
            try:
                audit(target)
            except ValueError as error:
                if 'source differs: overview.mkv' not in str(error):
                    raise
            else:
                raise AssertionError('Changed source hash accepted: ' + case)
        receipts.append({'case_id': case, 'construction_sha256': entry['construction_sha256'],
                         'source_record_sha256': positive['review_record_sha256'],
                         'frame_count': positive['frame_count'], 'negative_rejected': True})
    proof = {'format': 'c158196-selected-review-camera-delivery-proof-v1',
             'manifest_sha256': sha(ROOT / 'execution-manifest.json'),
             'cases': receipts, 'passed': True}
    path = ROOT / 'review-camera-delivery-proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    print('Independent source-bound camera review passed', len(receipts),
          'selected positives and changed-hash negatives')


if __name__ == '__main__':
    main()
