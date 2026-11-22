"""Source-bound synthetic physical outcome fixtures for one qualified sweep case."""
import argparse
import hashlib
import json
from pathlib import Path

from source_measurement import load_rows, measure
from sweep_case import ASSIGNMENT, SWEEPS

HERE = Path(__file__).resolve().parent
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(case_id, kind):
    if not case_id.startswith(ASSIGNMENT + '__') or kind not in KINDS:
        raise ValueError('Qualified sweep case and physical outcome required')
    short = case_id[len(ASSIGNMENT) + 2:]
    matches = [(name, spec) for name, spec in SWEEPS.items()
               if short.startswith(name + '-')]
    if len(matches) != 1 or short[-4:] not in ('0000', '0001', '0002'):
        raise ValueError('Unknown qualified sweep case')
    base = matches[0][1][0]
    source = HERE / 'fixtures' / (case_id + '-sources')
    actor, frame_map = source / 'native-actors.jsonl', source / 'video_frames.jsonl'
    rows = [dict(row) for row in load_rows(actor, frame_map)]
    if len(rows) != 600:
        raise ValueError('Physical diagnostic requires 600 synchronized samples')
    if kind == 'incomplete_motion':
        for row in rows:
            row['ego_speed_mps'] = max(row['ego_speed_mps'], 1.0)
    elif kind == 'missing_evidence':
        rows[len(rows) // 2].pop('ego_lane_overlap')
    sources = {'diagnostic_actor_source_sha256': sha(actor),
               'diagnostic_frame_map_sha256': sha(frame_map),
               'fixture_transform': kind,
               'fixture_transform_code_sha256': sha(Path(__file__))}
    try:
        if any('ego_lane_overlap' not in row for row in rows):
            raise ValueError('Missing lane-footprint source evidence')
        observed = measure(rows)
        overlap = bool(observed['roadway_lane_overlap_frames'])
        status = ('met' if observed['complete_stop_observed'] and overlap ==
                  (base != 'contrast') else 'not_met')
        stop_frames = [row['frame'] for row in rows if row['ego_speed_mps'] <= 0.05]
        realized = {'sample_count': observed['sample_count'],
                    'roadway_stop_frame_count': len(stop_frames),
                    'lane_overlap_stop_frame_count': len(observed['roadway_lane_overlap_frames']),
                    'following_speed_drop_mps': observed['following_speed_drop_mps']}
        intervals = stop_frames[:1] + stop_frames[-1:] if stop_frames else []
        reason = 'sampled physical stop and placement observed' if status == 'met' else 'sampled physical stop or placement target not observed'
    except ValueError as error:
        if kind != 'missing_evidence':
            raise
        status, intervals, realized, reason = 'unverified', [], {}, str(error)
    if status != {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                  'missing_evidence': 'unverified'}[kind]:
        raise ValueError('Physical outcome fixture did not produce expected status')
    return {'case_id': case_id, 'fixture_kind': kind,
            'physical_checks': {'maneuver': {'status': status,
                'method': 'independent 20 Hz source-row stop and roadway-footprint check',
                'sources': sources, 'intervals': intervals, 'reason': reason,
                'legal_verdict_claimed': False}},
            'maneuver_completed': status == 'met', 'realized_observables': realized,
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'accepted': False, 'legal_verdict_claimed': False,
            'traffic_impediment_review': 'pending_original_source_review',
            'safe_operation_necessity_review': 'pending_original_source_review',
            'legal_compliance_review': 'pending_original_source_review'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=KINDS, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.case, args.kind)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(args.case, args.kind, result['physical_checks']['maneuver']['status'])
