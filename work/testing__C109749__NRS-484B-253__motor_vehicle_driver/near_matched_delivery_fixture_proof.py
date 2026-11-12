"""Exercise the selected near case on the matched 900-frame synthetic source.

Camera files are static CPU test patterns. They prove decoding and joins only;
they do not depict the changed opposing vehicle position or establish visibility.
"""
import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(FOLDER))
from approaching_delivery_audit import CAMERAS, audit_attempt, sha

CASE = 'testing__C109749__NRS-484B-253__motor_vehicle_driver__approaching_no_yield'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def finalizer():
    path = FOLDER / 'cases/approaching_no_yield/finalizer.py'
    spec = importlib.util.spec_from_file_location('near_matched_finalizer', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.finalize


def positive(root, near_root, media_root):
    if root.exists():
        raise ValueError('Use a fresh matched diagnostic root')
    attempt = root / 'attempt'
    attempt.mkdir(parents=True)
    for name in ('config.json', 'intersection_geometry.json', 'interaction_history.jsonl',
                 'video_frames.jsonl'):
        shutil.copy2(near_root / name, attempt / name)
    for name in ('trace.jsonl', 'capture/evidence.jsonl', 'raw.mkv',
                 *(camera + '.mkv' for camera in CAMERAS)):
        dest = attempt / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(media_root / name, dest)
    write(attempt / 'acquisition-provenance.json',
          {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
           'scope': 'matched 900-frame CPU source; static pattern cameras depict no actors'})
    finalizer()(attempt, attempt / 'analysis-report.json')
    result = json.loads((attempt / 'result.json').read_text())
    if (result.get('diagnostic_fixture') is not True or
            result.get('physical_acceptance_claimed') is not False or
            result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met'):
        raise ValueError('Matched near finalizer did not retain diagnostic physical status')
    mapping = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    history = [json.loads(line) for line in (attempt / 'interaction_history.jsonl').read_text().splitlines()]
    write(attempt / 'converted/trace.json',
          {'scenes': [{'t': round(row['time_s'] * 1000)} for row in mapping]})
    required = ('config.json', 'intersection_geometry.json', 'interaction_history.jsonl',
                'video_frames.jsonl', 'trace.jsonl',
                *(camera + '.mkv' for camera in CAMERAS))
    write(attempt / 'capture-seal.json',
          {'format': 'worker-sealed-capture', 'provenance_kind': 'synthetic_fixture',
           'diagnostic_fixture': True, 'frames': len(mapping),
           'sources': {name: sha(attempt / name) for name in required},
           'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
           'physical_acceptance_claimed': False})
    write(attempt / 'native-exit.json',
          {'event': 'native_exit', 'capture_seal_sha256': sha(attempt / 'capture-seal.json')})
    write(attempt / 'owner-release.json',
          {'event': 'owner_released', 'operator_attested': True,
           'native_exit_sha256': sha(attempt / 'native-exit.json'),
           'diagnostic_fixture': True})
    samples = (0, 41, 116, 899)
    review = {'case_id': CASE, 'reviewer': 'synthetic CPU fixture generator',
              'method': 'static red test pattern; no actor identity or real visibility assertion',
              'frame_map_sha256': sha(attempt / 'video_frames.jsonl'),
              'source_sha256': {name: sha(attempt / (name + '.mkv')) for name in CAMERAS},
              'observations': [
                  {'camera': name, 'video_frame': index, 'actor': role,
                   'actor_id': history[index][role]['actor_id'],
                   'bbox_xyxy': [0, 0, 100, 100]}
                  for name in CAMERAS for index in samples
                  for role in ('ego', 'oncoming', 'reciprocal')]}
    write(root / 'pixel-review.json', review)
    receipt = audit_attempt(attempt, CASE, 'diagnostic-job', 1,
                            'diagnostic-recording', root / 'pixel-review.json',
                            attempt / 'matched-diagnostic-audit.json',
                            root / 'source-decode.json', diagnostic_selftest=True)
    if (receipt['passed'] is not False or receipt['software_checks_passed'] is not True or
            receipt['frames'] != 900):
        raise ValueError('Matched near audit claimed physical acceptance or wrong duration')
    print(json.dumps({'case_id': CASE, 'frames': receipt['frames'],
                      'software_checks_passed': True, 'diagnostic_fixture': True,
                      'physical_acceptance_claimed': False,
                      'audit_sha256': sha(attempt / 'matched-diagnostic-audit.json')},
                     sort_keys=True))


def negative(root, source_root):
    if root.exists():
        raise ValueError('Use a fresh negative diagnostic root')
    source = source_root / 'attempt'
    if not (source / 'matched-diagnostic-audit.json').is_file():
        raise ValueError('Positive matched near audit required first')
    attempt = root / 'attempt'
    attempt.mkdir(parents=True)
    for name in ('config.json', 'result.json', 'capture-seal.json', 'native-exit.json',
                 'owner-release.json'):
        shutil.copy2(source / name, attempt / name)
    audit_attempt(attempt, CASE, 'diagnostic-job', 1, 'diagnostic-recording',
                  source_root / 'pixel-review.json',
                  attempt / 'matched-diagnostic-audit.json',
                  root / 'source-decode.json', diagnostic_selftest=True)
    raise ValueError('Missing sealed original was accepted')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--near-root', type=Path)
    parser.add_argument('--media-root', type=Path)
    parser.add_argument('--negative-source-root', type=Path)
    args = parser.parse_args()
    if args.case != CASE:
        raise ValueError('Exact matched near case required')
    if args.negative_source_root:
        negative(args.output_root.resolve(), args.negative_source_root.resolve())
    else:
        if args.near_root is None or args.media_root is None:
            raise ValueError('Near source and diagnostic media roots required')
        positive(args.output_root.resolve(), args.near_root.resolve(),
                 args.media_root.resolve())


if __name__ == '__main__':
    main()
