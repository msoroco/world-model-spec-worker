"""CPU-test exact saved-source joins and negative rejection for one case."""
import argparse
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent
MANIFEST = PACKAGE / 'draft-primary-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(case_id, reject_frame_join):
    manifest = json.loads(MANIFEST.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == case_id)
    suffix = case_id.rsplit('__', 1)[-1]
    folder = PACKAGE / 'diagnostic-fixture' / suffix
    source = folder / 'sources'
    trace = [json.loads(row) for row in (source / 'trace.jsonl').read_text().splitlines()]
    raw = [json.loads(row) for row in (source / 'native-raw-actors.jsonl').read_text().splitlines()]
    frames = [json.loads(row) for row in (source / 'video_frames.jsonl').read_text().splitlines()]
    if reject_frame_join:
        frames[-1] = dict(frames[-1], native_frame=frames[-1]['native_frame'] + 1)
    if len(trace) != len(raw) or len(raw) != len(frames) or len(trace) != 600:
        raise ValueError('Original actor/frame/trace count differs')
    for index, (pose, actor, frame) in enumerate(zip(trace, raw, frames)):
        if (pose['frame'] != actor['native_frame'] or
                pose['frame'] != frame['native_frame'] or
                actor['frame'] != frame['video_frame'] or
                abs(pose['time_s'] - frame['time_s']) > 1e-6):
            raise ValueError('Original actor/frame/trace join differs at ' + str(index))
    construction = PACKAGE / entry['construction']
    if sha(construction) != entry['construction_sha256']:
        raise ValueError('Selected construction changed')
    positive_path = folder / 'attempt-primary-atoms.log'
    saved_path = folder / 'saved-primary-atoms.log'
    positive = json.loads(positive_path.read_text())
    saved = json.loads(saved_path.read_text())
    if (positive.get('passed') is not True or saved.get('passed') is not True or
            saved.get('recorded_only') is not True or
            positive.get('case_id') != case_id or saved.get('case_id') != case_id or
            positive.get('construction_sha256') != entry['construction_sha256']):
        raise ValueError('Current saved/compatibility receipt differs')
    if positive.get('negative_removed') != 'reviewed-curb.json':
        raise ValueError('Missing required-source rejection')
    return {'case_id': case_id, 'passed': True, 'source_join_frames': 600,
            'source_kind': 'synthetic_native_sample',
            'compatibility_receipt_sha256': sha(positive_path),
            'saved_receipt_sha256': sha(saved_path),
            'diagnostic_only': True, 'accepted': False,
            'original_native_observed': False, 'actual_pixels_verified': False,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--reject-frame-join', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.case, args.reject_frame_join)))
