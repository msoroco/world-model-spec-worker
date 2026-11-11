"""Independent original-source delivery audit for the 30.48 m signal case.

Synthetic selftests exercise software only. A passing live audit additionally
requires a sealed Native attempt, all planned frames, pixels and physical checks.
"""
import argparse
import json
import math
from pathlib import Path

from inside_delivery_audit import (CAMERAS, CHECKS, PROFILE, ROLES, media,
                                   read, review_checker, rows, sha,
                                   validate_inside_sequence, validate_originals)

CASE = 'testing__C109749__NRS-484B-253__motor_vehicle_driver__signal_advance_100_at'
TARGET_M = 30.48
MAX_OBSERVED_APPROACH_MPS = 20.0  # Engineering plausibility bound, not a legal speed limit.
DELIVERY_CHECKS = (*CHECKS, 'signal_advance')


def measure_signal_sequence(history, result):
    """Recompute the measured approach distance without calling the finalizer."""
    if len(history) < 3:
        raise ValueError('Original signal history too short')
    first = history[0]['ego_heading_deg']
    turn = next((i for i, row in enumerate(history)
                 if (row['ego_heading_deg'] - first + 180) % 360 - 180 <= -15), None)
    if turn is None or turn < 2:
        raise ValueError('Original left turn onset missing')
    if any((row['ego_heading_deg'] - first + 180) % 360 - 180 >= 15
           for row in history[:turn]):
        raise ValueError('Rightward heading change precedes left turn')
    if not history[turn]['ego_left_indicator']:
        raise ValueError('Left indicator absent at turn')
    onset = turn
    while onset and history[onset - 1]['ego_left_indicator']:
        onset -= 1
    if onset == 0 or onset >= turn:
        raise ValueError('Complete signal onset not retained')
    if history[onset - 1]['ego_left_indicator']:
        raise ValueError('Signal onset did not follow an observed off state')
    positions = []
    previous = None
    for row in history:
        position = row.get('ego', {}).get('position_xy_m')
        if (not isinstance(position, list) or len(position) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v)
                    for v in position)):
            raise ValueError('Original ego position missing')
        positions.append(position)
        if previous is not None:
            frame_delta = row.get('frame') - previous.get('frame')
            time_delta = row.get('time_s') - previous.get('time_s')
            if frame_delta != 1 or not math.isclose(time_delta, 0.05, abs_tol=0.002):
                raise ValueError('Original 20 Hz frame cadence differs')
            if (len(positions) - 1 < turn and
                    math.dist(previous['ego']['position_xy_m'], position) >
                    MAX_OBSERVED_APPROACH_MPS * time_delta + 1e-6):
                raise ValueError('Original preturn position jump exceeds engineering bound')
        previous = row
    # Both endpoints precede the first turning sample. The detector's turn
    # segment contributes no advance distance.
    distance = math.fsum(math.dist(positions[i - 1], positions[i])
                         for i in range(onset + 1, turn))
    if distance < TARGET_M:
        raise ValueError('Original continuous signal distance below 30.48 m')
    saved = result.get('measured_values', {})
    if (type(saved.get('observed_continuous_signal_advance_m')) not in (int, float)
            or not math.isclose(saved['observed_continuous_signal_advance_m'],
                                distance, rel_tol=0, abs_tol=1e-6)):
        raise ValueError('Saved signal distance differs from original source')
    target = next((x for x in result.get('target_checks', [])
                   if x.get('target') == 'continuous_left_signal_at_least_30_48_m'), None)
    if (not target or target.get('requested') is not True or
            target.get('measured') is not True or
            target.get('matched') is not True):
        raise ValueError('Saved signal target check differs from original source')
    return {'observed_continuous_approach_distance_m': distance,
            'continuous_start_frame': history[onset]['frame'],
            'turn_frame': history[turn]['frame'],
            'last_prechange_frame': history[turn - 1]['frame'],
            'full_signal_onset_observed': True,
            'observable_30_48_m_met': True,
            'legal_verdict_asserted': False}


def audit_attempt(attempt, case_id, job_id, attempt_number, recording_id,
                  pixel_review, output, decode_receipt, *, diagnostic_selftest=False):
    if case_id != CASE:
        raise ValueError('Unsupported exact C109749 signal-advance case')
    root = Path(attempt).resolve()
    output = Path(output).resolve()
    decode_receipt = Path(decode_receipt).resolve()
    if output.name == 'result.json' or root not in output.parents or root in decode_receipt.parents:
        raise ValueError('Audit output must remain under attempt; decode receipt must be external')
    result = read(root / 'result.json')
    kind = 'synthetic_fixture' if diagnostic_selftest else 'native'
    if (result.get('case_id') != case_id or result.get('provenance_kind') != kind or
            result.get('diagnostic_fixture') is not diagnostic_selftest or
            result.get('physical_acceptance_claimed') is not False):
        raise ValueError('Exact source provenance and result required')
    seal = read(root / 'capture-seal.json')
    if (seal.get('format') != 'worker-sealed-capture' or
            seal.get('provenance_kind') != kind or
            seal.get('diagnostic_fixture') is not diagnostic_selftest):
        raise ValueError('Exact sealed capture required')
    required = {'config.json', 'interaction_history.jsonl', 'intersection_geometry.json',
                'video_frames.jsonl', 'trace.jsonl',
                *(name + '.mkv' for name in CAMERAS)}
    if not required <= set(seal.get('sources', {})):
        raise ValueError('Capture seal omits required original source')
    for name, digest in seal['sources'].items():
        source = (root / name).resolve()
        if root not in source.parents or not source.is_file() or sha(source) != digest:
            raise ValueError('Sealed original source changed: ' + name)
    if read(root / 'native-exit.json').get('capture_seal_sha256') != sha(root / 'capture-seal.json'):
        raise ValueError('Native exit does not bind capture seal')
    owner = read(root / 'owner-release.json')
    if owner.get('operator_attested') is not True or owner.get('native_exit_sha256') != sha(root / 'native-exit.json'):
        raise ValueError('Owner release does not bind Native exit')
    joined = validate_originals(root, case_id)
    physical = result.get('physical_checks', {})
    if (physical.get('setup', {}).get('status') != 'met' or
            physical.get('maneuver', {}).get('status') != 'met' or
            not result.get('realized_observables')):
        raise ValueError('Source-bound physical completion absent')
    history = rows(root / 'interaction_history.jsonl')
    signal = measure_signal_sequence(history, result)
    junction = validate_inside_sequence(root, 'yield', result)
    sources = {name: root / (name + '.mkv') for name in CAMERAS}
    media.check_four_view_sources(sources)
    review = read(pixel_review)
    if (not review.get('reviewer') or not review.get('method') or review.get('case_id') != case_id or
            review.get('frame_map_sha256') != joined['frame_map_sha256'] or
            review.get('source_sha256') != {name: sha(path) for name, path in sources.items()}):
        raise ValueError('Independent pixel review missing or stale')
    observations = review.get('observations', [])
    if (not observations or {x.get('actor') for x in observations} != set(ROLES) or
            not all(any(x.get('camera') == name for x in observations) for name in CAMERAS)):
        raise ValueError('Independent pixel review omits actor or camera')
    for row in observations:
        i = row.get('video_frame')
        if (type(i) is not int or not 0 <= i < len(history) or
                row.get('actor') not in ROLES or row.get('camera') not in CAMERAS or
                row.get('actor_id') != history[i][row['actor']]['actor_id']):
            raise ValueError('Pixel review differs from original actor/frame')
    sizes = {'overview': PROFILE['overview'], **dict(zip(CAMERAS[1:], PROFILE['detail_views']))}
    for name, path in sources.items():
        sample = [x for x in observations if x['camera'] == name]
        check, finish = review_checker(sample, *sizes[name])
        media.audit(path, joined['frames'],
                    checkers={'reviewed_actor_pixels': (sha(__file__), check)},
                    mapping_sha256=joined['frame_map_sha256'])
        finish()
    decoded = media.audit(root / 'raw.mkv', joined['frames'],
                          mapping_sha256=joined['frame_map_sha256'], receipt=decode_receipt)
    scenes = read(root / 'converted/trace.json')['scenes']
    mapping = rows(root / 'video_frames.jsonl')
    if len(scenes) != joined['frames'] or any(
            scene['t'] != round(frame['time_s'] * 1000)
            for scene, frame in zip(scenes, mapping)):
        raise ValueError('Core trace/original frame time join differs')
    receipt = {'format': 'worker-delivery-audit-diagnostic' if diagnostic_selftest else 'worker-delivery-audit',
               'passed': not diagnostic_selftest, 'software_checks_passed': True,
               'diagnostic_fixture': diagnostic_selftest, 'physical_acceptance_claimed': False,
               'case_id': case_id, 'job_id': job_id, 'attempt': attempt_number,
               'recording_id': recording_id, 'checks': {key: True for key in DELIVERY_CHECKS},
               'frames': joined['frames'], 'original_sources': joined,
               'signal_advance': signal, 'inside_sequence': junction,
               'source_result_sha256': sha(root / 'result.json'),
               'video': 'raw.mkv', 'video_sha256': sha(root / 'raw.mkv'),
               'trace': 'converted/trace.json',
               'trace_sha256': sha(root / 'converted/trace.json'),
               'auditor_path': str(Path(__file__).resolve()), 'auditor_sha256': sha(__file__),
               'source_decode_receipt_path': str(decode_receipt),
               'source_decode_receipt_sha256': sha(decode_receipt),
               'source_decode_auditor_sha256': decoded['auditor_sha256'],
               'pixel_review_sha256': sha(pixel_review)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser()
    for name in ('case', 'attempt', 'job-id', 'recording-id', 'pixel-review',
                 'output', 'decode-receipt'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--attempt-number', type=int, required=True)
    parser.add_argument('--diagnostic-selftest', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit_attempt(args.attempt, args.case, args.job_id,
                                   args.attempt_number, args.recording_id,
                                   args.pixel_review, args.output,
                                   args.decode_receipt,
                                   diagnostic_selftest=args.diagnostic_selftest),
                     sort_keys=True))


if __name__ == '__main__':
    main()
