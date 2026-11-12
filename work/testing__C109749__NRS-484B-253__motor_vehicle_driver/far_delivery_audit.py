"""Independent full-source audit for the C109749 far-approach exact case.

Diagnostic mode exercises the audit on synthetic pixels and never passes a
physical delivery. Live mode requires Native provenance and independent review.
"""
import argparse
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon

from approaching_delivery_audit import (
    CAMERAS, CHECKS, PROFILE, ROLES, read, review_checker, rows, sha,
    validate_originals,
)
from worker_exchange import media

CASE = 'testing__C109749__NRS-484B-253__motor_vehicle_driver__approaching_far'


def far_sequence(root, result):
    """Recompute turn, opposing entry, and closing time from retained bodies."""
    config = read(root / 'config.json')
    geometry = read(root / 'intersection_geometry.json')
    polygon = Polygon(geometry['intersection_polygon_xy_m'])
    history = rows(root / 'interaction_history.jsonl')
    if not polygon.is_valid or polygon.is_empty or config.get('hazard_legal_threshold', 'missing') is not None:
        raise ValueError('Original far geometry or legal threshold differs')
    direction = geometry['oncoming_direction_xy']
    conflict = geometry['conflict_point_xy_m']
    if (not isinstance(direction, list) or len(direction) != 2 or
            not 0.9 <= math.hypot(*direction) <= 1.1):
        raise ValueError('Original opposing approach direction invalid')
    release = config.get('controller_release_ttc_s')
    if isinstance(release, bool) or not isinstance(release, (int, float)) or release <= 0:
        raise ValueError('Engineering release setting invalid')

    def intersects(row, role):
        return polygon.intersects(MultiPoint(row[role]['body_vertices_xy_m']).convex_hull)

    initial_heading = history[0]['ego_heading_deg']
    turn = next((row['frame'] for row in history
                 if abs((row['ego_heading_deg'] - initial_heading + 180) % 360 - 180) >= 15), None)
    entry = next((row['frame'] for row in history if intersects(row, 'oncoming')), None)
    if turn is None or entry is None or turn >= entry:
        raise ValueError('Far turn must precede opposing body entry')
    if any(intersects(row, 'oncoming') for row in history if row['frame'] <= turn):
        raise ValueError('Opposing complete body entered before far turn')
    sample = next(row for row in history if row['frame'] == turn)
    if not sample['ego_left_indicator']:
        raise ValueError('Left indicator absent at far turn')
    opposing = sample['oncoming']
    remaining = sum((conflict[i] - opposing['position_xy_m'][i]) * direction[i] for i in (0, 1))
    closing = sum(opposing['velocity_xy_mps'][i] * direction[i] for i in (0, 1))
    if remaining <= 0 or closing <= 0.5:
        raise ValueError('Opposing source does not close toward conflict')
    time_to_conflict = remaining / closing
    if time_to_conflict < release:
        raise ValueError('Far source below engineering release margin')
    saved = result.get('measured_values', {})
    observed = {'frame': turn, 'remaining_distance_m': remaining,
                'closing_speed_mps': closing, 'kinematic_time_to_conflict_s': time_to_conflict}
    prior = saved.get('turn_sample', {})
    if (saved.get('ego_turn_start_frame') != turn or saved.get('opposing_entry_frame') != entry or
            any(not math.isclose(prior.get(k, math.inf), v, rel_tol=0, abs_tol=1e-6)
                if isinstance(v, float) else prior.get(k) != v for k, v in observed.items())):
        raise ValueError('Saved far measurement differs from original bodies')
    return {'ego_turn_start_frame': turn, 'opposing_entry_frame': entry,
            'turn_sample': observed, 'engineering_release_ttc_s': release,
            'legal_verdict_asserted': False}


def audit_attempt(attempt, case_id, job_id, attempt_number, recording_id,
                  pixel_review, output, decode_receipt, *, diagnostic_selftest=False):
    if case_id != CASE:
        raise ValueError('Exact far-approach case required')
    root = Path(attempt).resolve()
    output = Path(output).resolve()
    decode_receipt = Path(decode_receipt).resolve()
    if output.name == 'result.json' or root not in output.parents or root in decode_receipt.parents:
        raise ValueError('Audit output must be under attempt; decode receipt external')
    result = read(root / 'result.json')
    kind = 'synthetic_fixture' if diagnostic_selftest else 'native'
    if (result.get('case_id') != case_id or result.get('provenance_kind') != kind or
            result.get('diagnostic_fixture') is not diagnostic_selftest or
            result.get('physical_acceptance_claimed') is not False):
        raise ValueError('Expected exact case and provenance')
    seal = read(root / 'capture-seal.json')
    if (seal.get('format') != 'worker-sealed-capture' or seal.get('provenance_kind') != kind or
            seal.get('diagnostic_fixture') is not diagnostic_selftest):
        raise ValueError('Capture seal provenance differs')
    required = {'config.json', 'intersection_geometry.json', 'interaction_history.jsonl',
                'video_frames.jsonl', 'trace.jsonl', *(name + '.mkv' for name in CAMERAS)}
    if not required <= set(seal.get('sources', {})):
        raise ValueError('Capture seal omits an original source')
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
    sequence = far_sequence(root, result)
    sources = {name: root / (name + '.mkv') for name in CAMERAS}
    media.check_four_view_sources(sources)
    review = read(pixel_review)
    if (not review.get('reviewer') or not review.get('method') or review.get('case_id') != case_id or
            review.get('frame_map_sha256') != joined['frame_map_sha256'] or
            review.get('source_sha256') != {name: sha(path) for name, path in sources.items()}):
        raise ValueError('Independent pixel review missing or stale')
    observations = review.get('observations', [])
    if (not observations or {row.get('actor') for row in observations} != set(ROLES) or
            any(not any(row.get('camera') == name for row in observations) for name in CAMERAS)):
        raise ValueError('Pixel review omits actor or camera')
    history = rows(root / 'interaction_history.jsonl')
    sizes = {'overview': PROFILE['overview'], **dict(zip(CAMERAS[1:], PROFILE['detail_views']))}
    for row in observations:
        index = row.get('video_frame')
        role = row.get('actor')
        if (type(index) is not int or not 0 <= index < len(history) or role not in ROLES or
                row.get('camera') not in CAMERAS or row.get('actor_id') != history[index][role]['actor_id']):
            raise ValueError('Reviewed actor identity lacks original frame join')
    for name, path in sources.items():
        check, finish = review_checker([row for row in observations if row['camera'] == name], *sizes[name])
        media.audit(path, joined['frames'], checkers={'reviewed_actor_pixels': (sha(__file__), check)},
                    mapping_sha256=joined['frame_map_sha256'])
        finish()
    primary = root / 'raw.mkv'
    decoded = media.audit(primary, joined['frames'], mapping_sha256=joined['frame_map_sha256'],
                          receipt=decode_receipt)
    trace = root / 'converted/trace.json'
    scenes = read(trace)['scenes']
    mapping = rows(root / 'video_frames.jsonl')
    if len(scenes) != joined['frames'] or any(scene['t'] != round(frame['time_s'] * 1000)
                                               for scene, frame in zip(scenes, mapping)):
        raise ValueError('Core trace/original frame time join differs')
    receipt = {'format': 'worker-delivery-audit-diagnostic' if diagnostic_selftest else 'worker-delivery-audit',
               'passed': not diagnostic_selftest, 'software_checks_passed': True,
               'diagnostic_fixture': diagnostic_selftest, 'physical_acceptance_claimed': False,
               'case_id': case_id, 'job_id': job_id, 'attempt': attempt_number,
               'recording_id': recording_id, 'checks': {name: True for name in CHECKS},
               'frames': joined['frames'], 'far_sequence': sequence,
               'original_sources': joined, 'source_result_sha256': sha(root / 'result.json'),
               'video': 'raw.mkv', 'video_sha256': sha(primary),
               'trace': 'converted/trace.json', 'trace_sha256': sha(trace),
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
    for name in ('case', 'attempt', 'job-id', 'recording-id', 'pixel-review', 'output', 'decode-receipt'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--attempt-number', type=int, required=True)
    parser.add_argument('--diagnostic-selftest', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit_attempt(args.attempt, args.case, args.job_id, args.attempt_number,
                                   args.recording_id, args.pixel_review, args.output,
                                   args.decode_receipt, diagnostic_selftest=args.diagnostic_selftest),
                     sort_keys=True))


if __name__ == '__main__':
    main()
