"""Independent CPU physical-stop fixtures; never a Native or legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from source_measurement import load_rows, measure


ROOT = Path(__file__).resolve().parent
EXPECTED_OVERLAP = {
    'reference': True, 'contrast': False,
    'safe_operation_stop': True, 'law_required_stop': True,
}
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evaluate(case, kind):
    if case not in EXPECTED_OVERLAP or kind not in KINDS:
        raise ValueError('Unknown case or physical fixture kind')
    source = ROOT / 'fixtures' / (case + '-sources')
    actor = source / 'native-actors.jsonl'
    frame_map = source / 'video_frames.jsonl'
    rows = load_rows(actor, frame_map)
    # Negative fixtures alter a copy of the diagnostic source rows. The original
    # evidence and its digest remain unchanged and cannot be mistaken for Native.
    rows = [dict(row) for row in rows]
    if kind == 'incomplete_motion':
        for row in rows:
            row['ego_speed_mps'] = max(row['ego_speed_mps'], 1.0)
    elif kind == 'missing_evidence':
        rows[len(rows)//2].pop('ego_lane_overlap')
    sources = {
        'diagnostic_actor_source_sha256': digest(actor),
        'diagnostic_frame_map_sha256': digest(frame_map),
        'fixture_transform': kind,
        'fixture_transform_code_sha256': digest(__file__),
    }
    try:
        if len(rows) != 600:
            raise ValueError('Physical diagnostic requires 600 synchronized samples')
        if any('ego_lane_overlap' not in row for row in rows):
            raise ValueError('Missing lane-footprint source evidence')
        observed = measure(rows)
        stop = observed['complete_stop_observed']
        overlap = bool(observed['roadway_lane_overlap_frames'])
        met = stop and overlap == EXPECTED_OVERLAP[case]
        status = 'met' if met else 'not_met'
        reason = ('sampled physical stop and placement observed' if met else
                  'sampled physical stop or placement target not observed')
        interval = [row['frame'] for row in rows if row['ego_speed_mps'] <= 0.05]
        realized = {
            'sample_count': observed['sample_count'],
            'roadway_stop_frame_count': len(interval),
            'lane_overlap_stop_frame_count': len(observed['roadway_lane_overlap_frames']),
            'following_speed_drop_mps': observed['following_speed_drop_mps'],
        }
    except ValueError as error:
        if kind != 'missing_evidence':
            raise
        status, reason, interval, realized = 'unverified', str(error), [], {}
    if status != {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                  'missing_evidence': 'unverified'}[kind]:
        raise ValueError('Physical diagnostic fixture did not produce expected outcome')
    return {
        'case_id': 'training__C179480__NRS-484B-627-2__motor_vehicle_driver__' + case,
        'fixture_kind': kind,
        'physical_checks': {'maneuver': {
            'status': status,
            'method': 'independent 20 Hz source-row stop and roadway-footprint check',
            'sources': sources,
            'intervals': interval[:1] + interval[-1:] if interval else [],
            'reason': reason,
            'legal_verdict_claimed': False,
        }},
        'maneuver_completed': status == 'met',
        'realized_observables': realized,
        'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True,
        'accepted': False,
        'legal_verdict_claimed': False,
        'traffic_impediment_review': 'pending_original_source_review',
        'safe_operation_necessity_review': 'pending_original_source_review',
        'legal_compliance_review': 'pending_original_source_review',
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True, choices=EXPECTED_OVERLAP)
    parser.add_argument('--kind', required=True, choices=KINDS)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.case, args.kind)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(args.case, args.kind, result['physical_checks']['maneuver']['status'])


if __name__ == '__main__':
    main()
