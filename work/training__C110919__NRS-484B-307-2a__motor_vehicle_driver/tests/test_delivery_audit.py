"""Source-shaped fake Native originals exercise the physical audit branch only."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/owner194-next'
assert Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve().is_relative_to(ROOT / '.runtime-work')
spec = importlib.util.spec_from_file_location('delivery_audit', HERE / 'delivery_audit.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
case = HERE.name + '__controlled_1'
source = SCRATCH / 'rebuilt-1-primary-compat-v2'
with tempfile.TemporaryDirectory(prefix='owner194-physical-audit-', dir=ROOT / '.runtime-work') as temporary:
    attempt = Path(temporary)
    for name in ('trace.jsonl', 'capture/evidence.jsonl', 'video_frames.jsonl',
                 'native_samples.jsonl', 'body_history.jsonl', 'road_geometry.json',
                 'road.xodr',
                 'capture/manifest.json', 'analysis-report.json', 'result.json'):
        path = attempt / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, path)
    for camera in module.CAMERAS:
        (attempt / (camera + '.mkv')).symlink_to(source / (camera + '.mkv'))
    capture = json.loads((attempt / 'capture/manifest.json').read_text())
    capture['synthetic_diagnostic'] = False
    (attempt / 'capture/manifest.json').write_text(json.dumps(capture) + '\n')
    result = json.loads((attempt / 'result.json').read_text())
    result['provenance_kind'] = 'native'
    (attempt / 'result.json').write_text(json.dumps(result) + '\n')
    (attempt / 'native-capture-report.json').write_text(json.dumps({
        'case_id': case, 'frames': 600, 'error': None,
        'restoration': {'synthetic_source_shape_test': True}, 'accepted': False}) + '\n')
    required = ('trace.jsonl', 'capture/evidence.jsonl', 'video_frames.jsonl',
                'native_samples.jsonl', 'body_history.jsonl', 'road_geometry.json',
                'capture/manifest.json', 'analysis-report.json', 'result.json',
                'native-capture-report.json')
    hashes = {name: module.sha(attempt / name) for name in required}
    hashes.update({camera + '.mkv': module.sha(attempt / (camera + '.mkv'))
                   for camera in module.CAMERAS})
    findings = {name: True for name in ('governing_circular_green_visible',
        'no_turn_prohibition_visible', 'pedestrian_lawful_context_reviewed',
        'vehicle_lawful_context_reviewed', 'full_body_and_conflict_visible',
        'yield_timing_reviewed')}
    review = attempt / 'pixel-review.json'
    review.write_text(json.dumps({'case_id': case, 'source_hashes': hashes,
                                  'reviewer': 'synthetic-source-shape-test',
                                  'findings': findings}) + '\n')
    assert module.audit(case, attempt, 'physical', review, None)['physical_checks_passed'] is True
    stale = json.loads(review.read_text())
    stale['source_hashes']['trace.jsonl'] = '0' * 64
    review.write_text(json.dumps(stale) + '\n')
    try:
        module.audit(case, attempt, 'physical', review, None)
    except ValueError as error:
        assert 'Pixel review is not bound' in str(error)
    else:
        raise AssertionError('Stale source-bound pixel review accepted')
    (attempt / 'overview.mkv').unlink()
    try:
        module.audit(case, attempt, 'physical', review, None)
    except ValueError as error:
        assert 'Missing source camera' in str(error)
    else:
        raise AssertionError('Missing original camera accepted')
print(json.dumps({'physical_branch_source_shape_test': 'passed',
                  'stale_review_rejected': True, 'missing_camera_rejected': True,
                  'diagnostic_fixture': True, 'native_or_physical_acceptance': False}))
