"""Source-shaped unit test for the future Native audit branch; never physical evidence."""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from delivery_audit import CAMERAS, audit


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


case_index = int(os.environ.get('OWNER199_SOURCE_SHAPE_CASE', '2'))
require(case_index in (2, 3), 'Source-shape test case must be above or exact at')
case = HERE.name + f'__controlled_{case_index}'
original = ROOT / f'.runtime-work/owner199/boundary-v2-{case_index}-primary-compat'
saved = ROOT / f'.runtime-work/owner199/boundary-v2-{case_index}-primary-saved/v0001/processing.json'
require(original.is_dir() and saved.is_file(), 'Selected source-shaped test inputs absent')
with tempfile.TemporaryDirectory(prefix='owner199-physical-audit-test-',
                                 dir=ROOT / '.runtime-work') as temporary:
    root = Path(temporary)
    attempt = root / 'attempt'
    attempt.mkdir()
    required = ('roundabout-survey.json', 'trace.jsonl', 'video_frames.jsonl',
                'capture/manifest.json', 'capture/evidence.jsonl',
                'capture/native/frames.jsonl',
                *(name + '.mkv' for name in CAMERAS))
    for name in required:
        target = attempt / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(original / name)
    rows = [json.loads(line) for line in
            (original / 'roundabout-speed-history.jsonl').read_text().splitlines()]
    for row in rows:
        row.pop('synthetic_diagnostic')
    history = attempt / 'roundabout-speed-history.jsonl'
    history.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    selection = json.loads((original / 'candidate-selection.json').read_text())
    selection['manifest_sha256'] = sha(HERE / 'execution-manifest.json')
    (attempt / 'candidate-selection.json').write_text(json.dumps(selection) + '\n')
    original_processing = json.loads(saved.read_text())
    original_result = json.loads(Path(original_processing['result']).read_text())
    original_result['provenance_kind'] = 'native'
    result_path = root / 'source-shaped-result.json'
    result_path.write_text(json.dumps(original_result) + '\n')
    original_processing['result'] = str(result_path)
    original_processing['result_sha256'] = sha(result_path)
    original_processing['original_source_hashes']['roundabout-speed-history.jsonl'] = sha(history)
    processing_path = root / 'source-shaped-processing.json'
    processing_path.write_text(json.dumps(original_processing) + '\n')
    review = {
        'format': 'worker-roundabout-visibility-review', 'case_id': case,
        'reviewer': 'CPU source-shape test only',
        'method': 'synthetic source-shaped unit test; no original pixels reviewed',
        'original_pixels_reviewed': True,
        'roundabout_arc_exit_visible': True, 'subject_visible': True,
        'cameras': {name: {'source_sha256': sha(attempt / (name + '.mkv')),
                           'frames': 600, 'vehicle_visible': True,
                           'road_context_visible': True} for name in CAMERAS}}
    review_path = root / 'source-shaped-review.json'
    review_path.write_text(json.dumps(review) + '\n')
    positive = audit(case, attempt, processing_path, False, review_path)
    require(positive['passed'] and positive['physical_completion'],
            'Future original-source branch did not execute')
    review['cameras']['overview']['source_sha256'] = '0' * 64
    review_path.write_text(json.dumps(review) + '\n')
    negative = False
    try:
        audit(case, attempt, processing_path, False, review_path)
    except ValueError as error:
        negative = 'Independent original camera review incomplete' in str(error)
    require(negative, 'Stale pixel review source did not reject')
    print(json.dumps({'format': 'worker-delivery-audit-source-shape-test',
                      'case_id': case,
                      'passed': True, 'physical_branch_exercised': True,
                      'stale_pixel_review_rejected': True,
                      'synthetic_cpu_fixture': True,
                      'physical_or_legal_acceptance': False}))
