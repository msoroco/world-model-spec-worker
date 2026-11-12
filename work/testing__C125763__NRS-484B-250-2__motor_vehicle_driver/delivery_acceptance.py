"""Independent prospective Native delivery audit for an exact C125763 case.

Diagnostic CPU attempts exercise the checks but cannot pass Native delivery.
The reviewer supplies original-frame actor boxes after examining the capture.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange import media  # noqa: E402
from worker_exchange.common import sha  # noqa: E402
from audit_delivery import audit as audit_sources  # noqa: E402
from capture_sources import CAMERAS  # noqa: E402
from runner import CASE_IDS  # noqa: E402

CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing original source: ' + path.name)
    return json.loads(path.read_text())


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing original source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def verify_seal(attempt, *, diagnostic=False):
    attempt = Path(attempt).resolve()
    seal = read(attempt / 'capture-seal.json')
    if (seal.get('format') != 'worker-sealed-capture' or
            seal.get('provenance_kind') != 'native' or
            seal.get('diagnostic_fixture') is not diagnostic or
            seal.get('restoration', {}).get('restored') is not True or
            not seal.get('encoder_exit_codes') or
            any(code != 0 for code in seal['encoder_exit_codes'].values())):
        raise ValueError('Native capture seal provenance or closure differs')
    needed = {'config.json', 'junction_context.json', 'crossing_history.jsonl',
              'controller_history.jsonl', 'video_frames.jsonl', 'trace.jsonl',
              'capture/evidence.jsonl', *(name + '.mkv' for name in CAMERAS)}
    sources = seal.get('sources')
    if not isinstance(sources, dict) or not needed <= set(sources):
        raise ValueError('Capture seal omits required original source')
    for name, digest in sources.items():
        source = (attempt / name).resolve()
        if attempt not in source.parents or not source.is_file() or sha(source) != digest:
            raise ValueError('Sealed original source changed: ' + name)
    native_exit = read(attempt / 'native-exit.json')
    if (native_exit.get('event') != 'native_exit' or
            native_exit.get('capture_seal_sha256') != sha(attempt / 'capture-seal.json') or
            native_exit.get('native_revision') != seal.get('native_revision')):
        raise ValueError('Native exit does not bind capture seal')
    owner = read(attempt / 'owner-release.json')
    if (owner.get('event') != 'owner_released' or
            owner.get('operator_attested') is not True or
            owner.get('native_exit_sha256') != sha(attempt / 'native-exit.json')):
        raise ValueError('Owner release does not bind Native exit')
    return seal


def verify_physical(result, attempt):
    attempt = Path(attempt).resolve()
    if result.get('physical_acceptance_claimed') is not False:
        raise ValueError('Result asserts physical acceptance before independent audit')
    for key in ('setup', 'target', 'maneuver'):
        check = result.get('physical_checks', {}).get(key, {})
        if check.get('status') != 'met' or not check.get('method'):
            raise ValueError('Source-bound physical completion absent: ' + key)
        sources = check.get('sources')
        if not isinstance(sources, dict) or not sources:
            raise ValueError('Physical completion source hashes absent: ' + key)
        for name, digest in sources.items():
            source = (attempt / name).resolve()
            if attempt not in source.parents or not source.is_file() or sha(source) != digest:
                raise ValueError('Physical completion source changed: ' + name)
    if (result.get('maneuver_completed') is not True or
            result.get('setup_confirmed') is not True or
            result.get('behavior_attempted') is not True):
        raise ValueError('Physical setup, selected target or maneuver not completed')


def pixel_checker(samples, width, height):
    pending = {}
    for sample in samples:
        pending.setdefault(sample['video_frame'], []).append(sample)
    seen = set()

    def check(frame):
        if (frame.width, frame.height) != (width, height):
            raise ValueError('Reviewed camera dimensions differ')
        for sample in pending.get(frame.index, []):
            box = sample.get('bbox_xyxy')
            if not isinstance(box, list) or len(box) != 4 or any(type(v) is not int for v in box):
                raise ValueError('Reviewed actor pixel box missing')
            x0, y0, x1, y1 = box
            if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height and
                    (x1 - x0) * (y1 - y0) >= 16):
                raise ValueError('Reviewed actor pixel box invalid')
            colors = set()
            for y in range(y0, y1):
                for x in range(x0, x1):
                    offset = 3 * (y * width + x)
                    colors.add(frame.pixels[offset:offset + 3])
                    if len(colors) >= 2:
                        break
                if len(colors) >= 2:
                    break
            if len(colors) < 2:
                raise ValueError('Reviewed actor ROI has no visible pixel detail')
            seen.add((frame.index, sample['actor_id']))

    def finish():
        if seen != {(s['video_frame'], s['actor_id']) for s in samples}:
            raise ValueError('Reviewed actor pixel frame was not decoded')

    return check, finish


def verify_review(attempt, case_id, review_path, frames):
    attempt = Path(attempt).resolve()
    review = read(review_path)
    source_hashes = {name: sha(attempt / (name + '.mkv')) for name in CAMERAS}
    if (review.get('case_id') != case_id or not review.get('reviewer') or
            not review.get('method') or
            review.get('frame_map_sha256') != sha(attempt / 'video_frames.jsonl') or
            review.get('source_sha256') != source_hashes):
        raise ValueError('Independent pixel review missing or stale')
    observations = review.get('observations', [])
    if (not observations or {row.get('actor') for row in observations} != {'ego', 'other'} or
            {row.get('camera') for row in observations} != set(CAMERAS)):
        raise ValueError('Independent pixel review omits actor or camera')
    history = rows(attempt / 'crossing_history.jsonl')
    if len(history) != frames:
        raise ValueError('Pixel review original history length differs')
    for row in observations:
        index = row.get('video_frame')
        if (type(index) is not int or not 0 <= index < frames or
                row.get('actor') not in ('ego', 'other') or
                row.get('actor_id') != history[index][row['actor']]['actor_id']):
            raise ValueError('Pixel review actor identity differs')
    for name, dimensions in CAMERAS.items():
        samples = [row for row in observations if row['camera'] == name]
        check, finish = pixel_checker(samples, *dimensions)
        media.audit(attempt / (name + '.mkv'), frames,
                    checkers={'reviewed_actor_pixels': (sha(__file__), check)},
                    mapping_sha256=sha(attempt / 'video_frames.jsonl'))
        finish()
    return sha(review_path)


def audit(attempt, case_id, pixel_review, output, *, diagnostic=False):
    attempt = Path(attempt).resolve()
    if case_id not in CASE_IDS:
        raise ValueError('Unknown exact C125763 case')
    seal = verify_seal(attempt, diagnostic=diagnostic)
    result = read(attempt / 'result.json')
    if (result.get('case_id') != case_id or
            result.get('provenance_kind') != 'native' or
            result.get('diagnostic_fixture') is not diagnostic):
        raise ValueError('Native result provenance differs')
    verify_physical(result, attempt)
    software = audit_sources(attempt, 'saved-analysis.json', decode=True,
                             expected_case=case_id)
    frames = software['original_frame_count']
    if seal.get('frames') != frames:
        raise ValueError('Sealed/original frame count differs')
    review_hash = verify_review(attempt, case_id, pixel_review, frames)
    media.audit(attempt / 'raw.mkv', frames,
                mapping_sha256=sha(attempt / 'video_frames.jsonl'))
    receipt = {'format': 'worker-c125763-delivery-audit', 'case_id': case_id,
               'passed': not diagnostic, 'diagnostic_fixture': diagnostic,
               'software_checks_passed': True, 'physical_acceptance_claimed': False,
               'checks': {key: True for key in CHECKS}, 'frames': frames,
               'source_audit': software, 'pixel_review_sha256': review_hash,
               'capture_seal_sha256': sha(attempt / 'capture-seal.json'),
               'owner_release_sha256': sha(attempt / 'owner-release.json'),
               'auditor_sha256': sha(__file__)}
    output = Path(output).resolve()
    if output.name == 'result.json' or attempt not in output.parents or output.exists():
        raise ValueError('Audit receipt must be a new separate file within attempt')
    output.write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--case', required=True)
    parser.add_argument('--pixel-review', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, args.pixel_review,
                           args.output, diagnostic=args.diagnostic), sort_keys=True))
