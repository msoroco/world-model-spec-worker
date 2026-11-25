"""Independent Native-source/pixel gate for the exact alley-width delivery case."""
import argparse
import hashlib
import json
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def source(root, name):
    p = (Path(root) / name).resolve()
    require(Path(root).resolve() in p.parents and p.is_file(), 'Missing original source: ' + name)
    return p


def check_result(result, case):
    require(result.get('case_id') == case and result.get('provenance_kind') == 'native'
            and result.get('diagnostic_fixture') is not True,
            'Missing original source: exact original Native result')
    require(result.get('accepted') is False and result.get('legal_verdict_claimed') is False,
            'Finalizer improperly accepted legal or physical outcome')
    maneuver = result.get('physical_checks', {}).get('maneuver', {})
    require(result.get('setup_confirmed') is True and result.get('maneuver_completed') is True
            and maneuver.get('status') == 'met' and maneuver.get('sources')
            and result.get('realized_observables'),
            'Original parking maneuver or setup not physically measured complete')
    measured = result.get('measured_values', {})
    require(measured.get('frame_count') == 600 and
            isinstance(measured.get('cross_section_free_width_m_by_frame'), list) and
            len(measured['cross_section_free_width_m_by_frame']) == 600 and
            measured.get('minimum_measured_halt_free_width_m') is not None and
            measured.get('legal_result') is None,
            'Missing continuous original free-width measurement')
    names = {r.get('name') for r in result.get('recording_evidence', [])}
    require({'st.alley', 'drv.standing_or_parked', 'st.lane_width', 'kin.extent',
             'rel.surface_gap', 'rel.occupies'} <= names,
            'Missing mandatory original alley observations')


def audit(attempt, case, output, review_name):
    import sys
    runtime = Path(__file__).resolve().parents[2] / 'runtime'
    sys.path[:0] = [str(runtime / 'scenario_pipeline'), str(runtime / 'python')]
    from worker_exchange.media import audit as media_audit, verify_receipt

    attempt = Path(attempt).resolve()
    result_path = source(attempt, 'result.json')
    result = json.loads(result_path.read_text())
    check_result(result, case)
    frame_map = source(attempt, 'video_frames.jsonl')
    poses = source(attempt, 'vehicle-poses.jsonl')
    inventory = source(attempt, 'alley-inventory.json')
    trace = source(attempt, 'trace.jsonl')
    review = json.loads(source(attempt, review_name).read_text())
    require(review.get('case_id') == case and review.get('source_kind') == 'original_native_review'
            and review.get('reviewer_id') and review.get('site_match_verified') is True
            and review.get('ordinance_effect_reviewed') is True
            and review.get('parking_purpose_verified') is True,
            'Missing independent original alley and ordinance review')
    for key, path in [('video_frames_sha256', frame_map), ('vehicle_poses_sha256', poses),
                      ('alley_inventory_sha256', inventory), ('trace_sha256', trace)]:
        require(review.get(key) == sha(path), 'Original review source changed: ' + key)
    frames = [json.loads(s) for s in frame_map.read_text().splitlines()]
    bodies = [json.loads(s) for s in poses.read_text().splitlines()]
    traces = [json.loads(s) for s in trace.read_text().splitlines()]
    require(len(frames) == len(bodies) == len(traces) == 600,
            'Original frame/body/trace count differs')
    for i, (frame, body, row) in enumerate(zip(frames, bodies, traces)):
        require(frame['video_frame'] == body['video_frame'] == i and
                frame['native_frame'] == body['native_frame'] == row['frame'] and
                abs(frame['time_s'] - body['time_s']) < .005 and
                abs(frame['time_s'] - row['time_s']) < .005 and
                body['subject']['vehicle_id'] != body['other']['vehicle_id'],
                'Original all-participant frame/time join differs')
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    decodes = {}
    for name in CAMERAS:
        video = source(attempt, name + '.mkv')
        receipt = output.with_name(output.stem + '-' + name + '-decode.json')
        media_audit(video, 600, mapping_sha256=sha(frame_map), receipt=receipt)
        verified = verify_receipt(video, receipt, 600, mapping_sha256=sha(frame_map))
        require(verified.get('rgb_sequence_sha256'), 'Original pixels not decoded')
        decodes[name] = {'video_sha256': sha(video), 'receipt_sha256': sha(receipt),
                         'rgb_sequence_sha256': verified['rgb_sequence_sha256']}
    payload = {'format': 'worker-delivery-audit', 'case_id': case, 'passed': True,
               'source_result_sha256': sha(result_path), 'review_sha256': sha(source(attempt, review_name)),
               'source_hashes': {'video_frames.jsonl': sha(frame_map),
                                 'vehicle-poses.jsonl': sha(poses),
                                 'alley-inventory.json': sha(inventory), 'trace.jsonl': sha(trace)},
               'video_decodes': decodes, 'checks': {name: True for name in CHECKS},
               'legal_verdict_claimed': False}
    output.write_text(json.dumps(payload, indent=2) + '\n')
    return payload


def self_test(case, negative):
    sample = {'case_id': case, 'provenance_kind': 'native', 'diagnostic_fixture': False,
              'accepted': False, 'legal_verdict_claimed': False,
              'setup_confirmed': True, 'maneuver_completed': True,
              'physical_checks': {'maneuver': {'status': 'met', 'sources': {'trace.jsonl': 'synthetic-test-hash'}}},
              'realized_observables': {'halt_duration_s': {'value': 5}},
              'measured_values': {'frame_count': 600,
                                  'cross_section_free_width_m_by_frame': [3.048] * 600,
                                  'minimum_measured_halt_free_width_m': 3.048,
                                  'legal_result': None},
              'recording_evidence': [{'name': n} for n in
                                     ('st.alley', 'drv.standing_or_parked', 'st.lane_width',
                                      'kin.extent', 'rel.surface_gap', 'rel.occupies')]}
    if negative:
        sample['provenance_kind'] = 'synthetic_fixture'
        check_result(sample, case)
        raise AssertionError('Synthetic fixture passed original-source gate')
    check_result(sample, case)
    for change in ({'maneuver_completed': False},
                   {'measured_values': {'frame_count': 9}},
                   {'realized_observables': {}}):
        altered = dict(sample, **change)
        try:
            check_result(altered, case)
        except ValueError:
            continue
        raise AssertionError('Incomplete original evidence passed')
    return {'case_id': case, 'passed': True,
            'source_predicates_tested': True, 'original_capture_attested': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--case', required=True)
    p.add_argument('--self-test', action='store_true')
    p.add_argument('--negative', action='store_true')
    p.add_argument('--attempt')
    p.add_argument('--output')
    p.add_argument('--review', default='alley-original-review.json')
    a = p.parse_args()
    print(json.dumps(self_test(a.case, a.negative) if a.self_test
                     else audit(a.attempt, a.case, a.output, a.review), indent=2))
