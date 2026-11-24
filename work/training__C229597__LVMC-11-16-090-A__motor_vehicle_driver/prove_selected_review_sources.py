"""Prove source integrity for both selected synthetic review pathways.

This checks evidence binding, not physical realization or a statutory judgment.
"""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from audit_saved_review_sources import audit
from measure_episode import finalize

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c229597-selected-review-source-proof'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reject(attempt, label, path, altered):
    original = path.read_bytes()
    path.write_bytes(altered(original))
    try:
        audit(attempt)
    except ValueError as error:
        result = {'name': label, 'rejected': True, 'error': str(error)}
    else:
        raise AssertionError(label + ' was accepted')
    finally:
        path.write_bytes(original)
    return result


def make_video(size, output):
    subprocess.run(('ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    'color=c=black:s=' + size + ':r=20', '-frames:v', '600',
                    '-c:v', 'ffv1', str(output)), check=True, timeout=180)


def one(case, manifest):
    attempt = SCRATCH / case
    attempt.mkdir(parents=True, exist_ok=True)
    fixture_path = HERE / f'selected-{case}-fixture.json'
    fixture = json.loads(fixture_path.read_text())
    for name in ('trace.jsonl', 'video_frames.jsonl', 'road.xodr',
                 'acquisition-provenance.json'):
        (attempt / name).write_text(fixture['files'][name])
    entry = next(row for row in manifest['cases'] if row['case_id'].endswith('__' + case))
    construction_path = HERE / entry['construction']
    if sha(construction_path) != entry['construction_sha256']:
        raise ValueError('Selected construction hash differs')
    construction = json.loads(construction_path.read_text())
    (attempt / 'construction.json').write_bytes(construction_path.read_bytes())
    config = next(row['content'] for row in construction['files'] if row['path'] == 'config.json')
    (attempt / 'config.json').write_text(config)
    shutil.copy2(SCRATCH / 'source-overview.mkv', attempt / 'overview.mkv')
    for view in VIEWS[1:]:
        shutil.copy2(SCRATCH / 'source-detail.mkv', attempt / (view + '.mkv'))
    finalize(attempt, attempt / 'analysis-report.json')
    positive = audit(attempt)
    negatives = [
        reject(attempt, 'changed_camera_bytes', attempt / 'approach.mkv',
               lambda value: value + b'changed'),
        reject(attempt, 'changed_road_bytes', attempt / 'road.xodr',
               lambda value: value + b'\n'),
        reject(attempt, 'changed_frame_map', attempt / 'video_frames.jsonl',
               lambda value: value + b'\n'),
    ]
    for source, field, false_value in (
        ('channels/original_highway_survey.json', 'highway_classification', 'highway'),
        ('channels/exhibition_episode_context.json', 'exhibition_review', 'exhibition'),
    ):
        path = attempt / source

        def forge(value, source=source, field=field, false_value=false_value):
            record = json.loads(value)
            record[Path(source).stem][field] = false_value
            return json.dumps(record).encode()

        negatives.append(reject(attempt, 'forged_' + field, path, forge))
    if audit(attempt) != positive:
        raise AssertionError('Restored source no longer passes')
    return {'case_id': entry['case_id'], 'fixture_sha256': sha(fixture_path),
            'construction_sha256': sha(construction_path), 'positive': positive,
            'negative_cases': negatives}


def main():
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    make_video('1920x1080', SCRATCH / 'source-overview.mkv')
    make_video('1280x720', SCRATCH / 'source-detail.mkv')
    manifest_path = HERE / 'selected-pair-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    rows = [one(case, manifest) for case in ('reference', 'contrast')]
    proof = {'format': 'c229597-selected-review-source-proof-v1',
             'manifest_sha256': sha(manifest_path),
             'auditor_sha256': sha(HERE / 'audit_saved_review_sources.py'),
             'finalizer_sha256': sha(HERE / 'measure_episode.py'),
             'selected_cases': rows, 'synthetic_fixture': True,
             'native_executed': False, 'physical_acceptance_claimed': False,
             'legal_verdict_claimed': False}
    output = HERE / 'selected-review-source-proof.json'
    output.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'selected_cases': len(rows),
                      'negative_rejections': sum(len(row['negative_cases']) for row in rows),
                      'proof_sha256': sha(output)}))


if __name__ == '__main__':
    main()
