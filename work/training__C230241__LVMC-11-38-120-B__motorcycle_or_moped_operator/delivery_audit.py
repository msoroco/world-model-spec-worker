"""Independently rehearse source joins and reject unobserved physical delivery."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def check(case_id, diagnostic):
    manifest = json.loads((HERE / 'selected-probe-manifest.json').read_text())
    entries = [entry for entry in manifest['cases'] if entry['case_id'] == case_id]
    if len(entries) != 1:
        raise ValueError('Select one exact case')
    if not diagnostic:
        raise ValueError('Original Native lamp pixels and calibrated reach required for delivery acceptance')
    case = case_id.rsplit('__', 1)[-1]
    source = HERE / 'selected-source' / case
    capture = rows(source / 'native-lighting-frames.jsonl')
    review = rows(source / 'lighting-review.jsonl')
    video_map = rows(source / 'video_frames.jsonl')
    if any(len(part) != 600 for part in (capture, review, video_map)):
        raise ValueError('Incomplete 600-frame source join')
    for index, (body, lamp, video) in enumerate(zip(capture, review, video_map)):
        if (body['native_frame'] != index or lamp['native_frame'] != index or
                body['video_frame'] != index or lamp['video_frame'] != index or
                abs(body['time_s'] - index / 20) > 1e-6 or
                abs(lamp['time_s'] - index / 20) > 1e-6 or
                video['native_frame'] != index):
            raise ValueError('Original frame/time join incomplete')
    context = json.loads((source / 'lighting-review-context.json').read_text())
    if context['source_kind'] != 'synthetic_native_sample' or not context['diagnostic_only']:
        raise ValueError('Unexpected source provenance')
    for name in ('native-lighting-frames.jsonl', 'video_frames.jsonl'):
        if sha(source / name) != context['source_sha256'][name]:
            raise ValueError('Source hash changed: ' + name)
    index = json.loads((HERE / 'selected-proofs/primary-index.json').read_text())
    item = next(row for row in index['cases'] if row['case_id'] == case_id)
    paths = item['proofs']
    for ref in paths.values():
        if sha(HERE / ref['path']) != ref['sha256']:
            raise ValueError('Public/saved proof changed')
    compatibility = json.loads((HERE / paths['compatibility']['path']).read_text())
    processing = json.loads((HERE / paths['processing']['path']).read_text())
    if (compatibility['case_id'] != case_id or
            compatibility['construction_sha256'] != entries[0]['construction_sha256'] or
            compatibility['candidate_id'] != 'primary' or not compatibility['passed'] or
            not {'native_validation', 'lean_decoder', 'final_decode', 'four_camera_sources',
                 'selected_measurements', 'negative_case_source'} <= set(compatibility['checks'])):
        raise ValueError('Primary public compatibility incomplete')
    if (not processing['passed'] or not processing['recorded_only'] or
            processing['timestamp_joins']['frames'] != 600 or
            processing['physical_acceptance_claimed'] is not False):
        raise ValueError('Recorded-only saved processing incomplete')
    return {'case_id': case_id, 'diagnostic_only': True, 'physical_acceptance': False,
            'legal_verdict': None, 'joined_frames': 600,
            'capture_sha256': sha(source / 'native-lighting-frames.jsonl'),
            'lamp_review_sha256': sha(source / 'lighting-review.jsonl'),
            'compatibility_sha256': paths['compatibility']['sha256'],
            'processing_sha256': paths['processing']['sha256']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.case, args.diagnostic), sort_keys=True))
