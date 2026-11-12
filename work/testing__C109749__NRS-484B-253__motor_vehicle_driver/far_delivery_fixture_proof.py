"""Prove far delivery audit software checks on full synthetic source media.

The positive receipt must say passed=false. The negative mode deliberately
removes a sealed original camera and must fail before any derived processing.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(FOLDER))
from prove_far_finalizer import finalize
from far_delivery_audit import CASE, CAMERAS, audit_attempt, sha


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def copy_originals(media_root, attempt):
    paths = ('config.json', 'intersection_geometry.json', 'interaction_history.jsonl',
             'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl',
             *(name + '.mkv' for name in CAMERAS), 'raw.mkv')
    for name in paths:
        source = media_root / name
        if not source.is_file():
            raise ValueError('Full-duration synthetic media source missing: ' + name)
        target = attempt / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def positive(root, media_root):
    if root.exists():
        raise ValueError('Use a fresh diagnostic output root')
    attempt = root / 'attempt'
    attempt.mkdir(parents=True)
    copy_originals(media_root, attempt)
    finalize(attempt, attempt / 'analysis-report.json')
    result = json.loads((attempt / 'result.json').read_text())
    if (result.get('provenance_kind') != 'synthetic_fixture' or
            result.get('diagnostic_fixture') is not True or
            result.get('physical_acceptance_claimed') is not False):
        raise ValueError('Far finalizer did not retain synthetic provenance')
    mapping = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    history = [json.loads(line) for line in (attempt / 'interaction_history.jsonl').read_text().splitlines()]
    write(attempt / 'converted/trace.json',
          {'scenes': [{'t': round(row['time_s'] * 1000)} for row in mapping]})
    required = ('config.json', 'intersection_geometry.json', 'interaction_history.jsonl',
                'video_frames.jsonl', 'trace.jsonl', *(name + '.mkv' for name in CAMERAS))
    sealed = {name: sha(attempt / name) for name in required}
    write(attempt / 'capture-seal.json',
          {'format': 'worker-sealed-capture', 'provenance_kind': 'synthetic_fixture',
           'diagnostic_fixture': True, 'frames': len(mapping), 'sources': sealed,
           'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
           'physical_acceptance_claimed': False})
    write(attempt / 'native-exit.json',
          {'event': 'native_exit', 'capture_seal_sha256': sha(attempt / 'capture-seal.json')})
    write(attempt / 'owner-release.json',
          {'event': 'owner_released', 'operator_attested': True,
           'native_exit_sha256': sha(attempt / 'native-exit.json'), 'diagnostic_fixture': True})
    samples = (0, 41, 116, 899)
    review = {'case_id': CASE, 'reviewer': 'synthetic CPU fixture generator',
              'method': 'static red test-pattern region; no actor identity or real visibility assertion',
              'frame_map_sha256': sha(attempt / 'video_frames.jsonl'),
              'source_sha256': {name: sha(attempt / (name + '.mkv')) for name in CAMERAS},
              'observations': [
                  {'camera': name, 'video_frame': index, 'actor': role,
                   'actor_id': history[index][role]['actor_id'], 'bbox_xyxy': [0, 0, 100, 100]}
                  for name in CAMERAS for index in samples for role in ('ego', 'oncoming', 'reciprocal')]}
    write(root / 'pixel-review.json', review)
    receipt = audit_attempt(attempt, CASE, 'diagnostic-job', 1, 'diagnostic-recording',
                            root / 'pixel-review.json', attempt / 'far-diagnostic-audit.json',
                            root / 'source-decode.json', diagnostic_selftest=True)
    if (receipt['passed'] is not False or receipt['software_checks_passed'] is not True or
            receipt['diagnostic_fixture'] is not True or receipt['frames'] != 900):
        raise ValueError('Far diagnostic audit incorrectly claimed physical acceptance')
    print(json.dumps({'case_id': CASE, 'frames': receipt['frames'],
                      'software_checks_passed': True, 'diagnostic_fixture': True,
                      'physical_acceptance_claimed': False,
                      'audit_sha256': sha(attempt / 'far-diagnostic-audit.json')}))


def negative(root, source_root):
    if root.exists():
        raise ValueError('Use a fresh negative diagnostic root')
    source = source_root / 'attempt'
    if not (source / 'far-diagnostic-audit.json').is_file():
        raise ValueError('Positive far diagnostic audit required first')
    attempt = root / 'attempt'
    attempt.mkdir(parents=True)
    names = ('config.json', 'result.json', 'capture-seal.json', 'native-exit.json',
             'owner-release.json', 'intersection_geometry.json', 'interaction_history.jsonl',
             'video_frames.jsonl', 'trace.jsonl', 'approach.mkv',
             'reference_corner.mkv', 'driver_reference.mkv')
    for name in names:
        shutil.copy2(source / name, attempt / name)
    audit_attempt(attempt, CASE, 'diagnostic-job', 1, 'diagnostic-recording',
                  source_root / 'pixel-review.json', attempt / 'far-diagnostic-audit.json',
                  root / 'source-decode.json', diagnostic_selftest=True)
    raise ValueError('Missing sealed overview camera was accepted')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--media-root', type=Path)
    parser.add_argument('--negative-source-root', type=Path)
    args = parser.parse_args()
    if args.case != CASE:
        raise ValueError('Exact far-approach case required')
    if args.negative_source_root:
        negative(args.output_root.resolve(), args.negative_source_root.resolve())
    else:
        if args.media_root is None:
            raise ValueError('Existing full-duration media root required')
        positive(args.output_root.resolve(), args.media_root.resolve())


if __name__ == '__main__':
    main()
