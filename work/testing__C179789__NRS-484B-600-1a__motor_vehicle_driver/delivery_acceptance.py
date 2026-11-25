"""Independent prospective Native source, physical and pixel acceptance audit."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ASSIGNMENT = 'testing__C179789__NRS-484B-600-1a__motor_vehicle_driver'
SUFFIXES = ('dry_4mps', 'dry_open_traffic', 'dry_6mps', 'wet_same_traffic',
            'narrow_same_traffic', 'dense_traffic', 'low_visibility', 'ice_or_snow')
CASES = {ASSIGNMENT + '__' + suffix for suffix in SUFFIXES}
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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


def verify_physical(result, attempt):
    attempt = Path(attempt).resolve()
    if result.get('physical_acceptance_claimed') is not False:
        raise ValueError('Physical acceptance asserted before independent audit')
    for key in ('setup', 'target', 'maneuver'):
        check = result.get('physical_checks', {}).get(key, {})
        if check.get('status') != 'met' or not check.get('method'):
            raise ValueError('Source-bound physical completion absent: ' + key)
        sources = check.get('sources')
        if not isinstance(sources, dict) or not sources:
            raise ValueError('Physical completion source hashes absent: ' + key)
        for name, digest in sources.items():
            path = (attempt / name).resolve()
            if attempt not in path.parents or not path.is_file() or sha(path) != digest:
                raise ValueError('Physical completion source changed: ' + name)
    if any(result.get(key) is not True for key in
           ('setup_confirmed', 'behavior_attempted', 'maneuver_completed')):
        raise ValueError('Selected target or maneuver incomplete')


def verify_originals(attempt, case):
    attempt = Path(attempt).resolve()
    result = read(attempt / 'result.json')
    if (result.get('case_id') != case or result.get('provenance_kind') != 'native'
            or result.get('diagnostic_fixture') is not False):
        raise ValueError('Original Native result identity or provenance differs')
    seal = read(attempt / 'capture-seal.json')
    if (seal.get('provenance_kind') != 'native' or seal.get('diagnostic_fixture') is not False
            or seal.get('restoration', {}).get('restored') is not True):
        raise ValueError('Native capture seal or restoration absent')
    required = {'config.json', 'condition_history.jsonl', 'road_context.json',
                'surface.txt', 'trace.jsonl', 'video_frames.jsonl',
                'capture/evidence.jsonl', *(name + '.mkv' for name in CAMERAS)}
    sources = seal.get('sources', {})
    if not required <= set(sources):
        raise ValueError('Native capture seal omits original speed or condition source')
    for name, digest in sources.items():
        path = (attempt / name).resolve()
        if attempt not in path.parents or not path.is_file() or sha(path) != digest:
            raise ValueError('Sealed original source changed: ' + name)
    native_exit = read(attempt / 'native-exit.json')
    owner = read(attempt / 'owner-release.json')
    if (native_exit.get('capture_seal_sha256') != sha(attempt / 'capture-seal.json')
            or owner.get('native_exit_sha256') != sha(attempt / 'native-exit.json')
            or owner.get('operator_attested') is not True):
        raise ValueError('Native exit or operator owner release differs')
    mapping = rows(attempt / 'video_frames.jsonl')
    history = rows(attempt / 'condition_history.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    if not mapping or len(mapping) != len(history) or len(mapping) != len(trace):
        raise ValueError('Original participant/time source lengths differ')
    for index, (frame, condition, motion) in enumerate(zip(mapping, history, trace)):
        if (frame.get('video_frame') != index or frame.get('carla_frame') != condition.get('frame')
                or frame.get('carla_frame') != motion.get('frame')
                or frame.get('time_s') != condition.get('time_s')
                or frame.get('time_s') != motion.get('time_s')
                or not condition.get('ego_actor_id') or not condition.get('surrounding_traffic')):
            raise ValueError('Original ego/lead/frame/time join differs')
    if seal.get('frames') != len(mapping):
        raise ValueError('Sealed frame count differs')
    verify_physical(result, attempt)
    return mapping, history


def audit(attempt, case, review_path, output):
    if case not in CASES:
        raise ValueError('Unknown exact speed/condition case')
    attempt = Path(attempt).resolve()
    mapping, history = verify_originals(attempt, case)
    from delivery_audit import audit_delivery
    condition_audit = audit_delivery(attempt, attempt / 'analysis-report.json')
    review = read(review_path)
    source_hashes = {name: sha(attempt / (name + '.mkv')) for name in CAMERAS}
    if (review.get('case_id') != case or not review.get('reviewer') or not review.get('method')
            or review.get('frame_map_sha256') != sha(attempt / 'video_frames.jsonl')
            or review.get('source_sha256') != source_hashes):
        raise ValueError('Independent pixel review missing or stale')
    observations = review.get('observations', [])
    if (not observations or {row.get('camera') for row in observations} != set(CAMERAS)
            or {row.get('actor') for row in observations} != {'ego', 'lead'}):
        raise ValueError('Independent pixel review omits camera or participant')
    config = read(attempt / 'config.json')
    dimensions = {c['name']: (c['width'], c['height']) for c in config['cameras']}
    repo = Path(__file__).resolve().parents[2]
    os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT',
                          str(repo / '.runtime-work/c179789-acceptance'))
    sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
    from worker_exchange import media
    for name in CAMERAS:
        samples = [row for row in observations if row['camera'] == name]
        seen = set()
        def inspect(frame):
            if (frame.width, frame.height) != dimensions[name]:
                raise ValueError('Reviewed camera dimensions differ')
            for sample in samples:
                if sample['video_frame'] != frame.index:
                    continue
                index = sample['video_frame']
                if not 0 <= index < len(history):
                    raise ValueError('Reviewed frame outside original history')
                actor = history[index]['ego_actor_id'] if sample['actor'] == 'ego' else history[index]['surrounding_traffic'][0]['actor_id']
                if sample.get('actor_id') != actor:
                    raise ValueError('Reviewed actor identity differs')
                box = sample.get('bbox_xyxy')
                if (not isinstance(box, list) or len(box) != 4
                        or any(type(v) is not int for v in box)):
                    raise ValueError('Reviewed actor box missing')
                x0, y0, x1, y1 = box
                if not (0 <= x0 < x1 <= frame.width and 0 <= y0 < y1 <= frame.height
                        and (x1 - x0) * (y1 - y0) >= 16):
                    raise ValueError('Reviewed actor box invalid')
                pixels = frame.pixels
                colors = set()
                for y in range(y0, y1):
                    for x in range(x0, x1):
                        offset = 3 * (y * frame.width + x)
                        colors.add(pixels[offset:offset + 3])
                        if len(colors) >= 2:
                            break
                    if len(colors) >= 2:
                        break
                if len(colors) < 2:
                    raise ValueError('Reviewed actor pixels lack visible detail')
                seen.add((index, actor))
        media.audit(attempt / (name + '.mkv'), len(mapping),
                    checkers={'reviewed_actor_pixels': (sha(__file__), inspect)},
                    mapping_sha256=sha(attempt / 'video_frames.jsonl'))
        if seen != {(row['video_frame'], row['actor_id']) for row in samples}:
            raise ValueError('Reviewed actor frame not decoded')
    media.audit(attempt / 'raw.mkv', len(mapping),
                mapping_sha256=sha(attempt / 'video_frames.jsonl'))
    receipt = {'format': 'worker-c179789-delivery-acceptance', 'case_id': case,
               'checks': {key: True for key in CHECKS}, 'passed': True,
               'source_hashes': source_hashes, 'frames': len(mapping),
               'condition_audit': condition_audit,
               'pixel_review_sha256': sha(review_path), 'auditor_sha256': sha(__file__)}
    output = Path(output).resolve()
    if output.exists() or attempt not in output.parents or output.name == 'result.json':
        raise ValueError('Acceptance receipt needs a new separate attempt path')
    output.write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--pixel-review', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, args.pixel_review, args.output)))
