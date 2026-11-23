"""Positive and tampered-source CPU checks for the saved review auditor."""
import hashlib
import json
import shutil
from pathlib import Path

from audit_saved_review_sources import audit
from measure_episode import finalize

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ATTEMPT = ROOT / '.runtime-work/c229597-review-source-audit/attempt'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expect_rejection(label, action):
    action()
    try:
        audit(ATTEMPT)
    except ValueError as error:
        return {'name': label, 'rejected': True, 'error': str(error)}
    raise AssertionError(label + ' was accepted')


def main():
    if ATTEMPT.parent.exists():
        shutil.rmtree(ATTEMPT.parent)
    ATTEMPT.mkdir(parents=True)
    source = json.loads((HERE / 'selected-reference-fixture.json').read_text())
    for name in ('trace.jsonl', 'video_frames.jsonl', 'road.xodr', 'acquisition-provenance.json'):
        (ATTEMPT / name).write_text(source['files'][name])
    shutil.copy2(HERE / 'config.json', ATTEMPT / 'config.json')
    shutil.copy2(HERE / 'construction.json', ATTEMPT / 'construction.json')
    shutil.copy2(ROOT / '.runtime-work/c229597-saved-v3-overview.mkv', ATTEMPT / 'overview.mkv')
    for name in ('approach', 'reference_corner', 'driver_reference'):
        shutil.copy2(ROOT / '.runtime-work/c229597-saved-v3-detail.mkv', ATTEMPT / (name + '.mkv'))
    finalize(ATTEMPT, ATTEMPT / 'analysis-report.json')
    positive = audit(ATTEMPT)
    negatives = []
    video = ATTEMPT / 'approach.mkv'
    original_video = video.read_bytes()
    negatives.append(expect_rejection('changed_camera_bytes',
                                      lambda: video.write_bytes(original_video + b'changed')))
    video.write_bytes(original_video)
    road = ATTEMPT / 'road.xodr'
    original_road = road.read_text()
    negatives.append(expect_rejection('changed_road_bytes',
                                      lambda: road.write_text(original_road + '\n')))
    road.write_text(original_road)
    context_path = ATTEMPT / 'channels/original_highway_survey.json'
    original_context = context_path.read_text()
    forged = json.loads(original_context)
    forged['original_highway_survey']['highway_classification'] = 'highway'
    negatives.append(expect_rejection('forged_highway_judgment',
                                      lambda: context_path.write_text(json.dumps(forged))))
    context_path.write_text(original_context)
    frame_map = ATTEMPT / 'video_frames.jsonl'
    original_map = frame_map.read_text()
    negatives.append(expect_rejection('changed_frame_map',
                                      lambda: frame_map.write_text(original_map + '\n')))
    frame_map.write_text(original_map)
    if audit(ATTEMPT) != positive:
        raise AssertionError('Restored source no longer passes')
    proof = {'format': 'c229597-review-source-cpu-proof-v1',
             'positive': positive, 'negative_cases': negatives,
             'auditor_sha256': sha(HERE / 'audit_saved_review_sources.py'),
             'finalizer_sha256': sha(HERE / 'measure_episode.py'),
             'fixture_sha256': sha(HERE / 'selected-reference-fixture.json'),
             'synthetic_fixture': True, 'native_executed': False,
             'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    (HERE / 'saved-review-source-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'positive': positive['review_source_integrity_passed'],
                      'negative_cases': len(negatives),
                      'proof_sha256': sha(HERE / 'saved-review-source-proof.json')}))


if __name__ == '__main__':
    main()
