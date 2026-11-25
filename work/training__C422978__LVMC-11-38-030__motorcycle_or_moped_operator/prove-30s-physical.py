"""Check three physical outcomes from source-bound synthetic motorcycle requests.

This exercises the prospective Native completion decision. It does not report
observed CARLA motion or a legal finding.
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def evaluate(rows, witness):
    if len(rows) != 600:
        return 'unverified', {}
    for frame, row in enumerate(rows):
        if (row.get('frame') != frame or row.get('time_s') != round(frame / 20, 4)
                or row.get('motorcycle_blueprint') != 'vehicle.kawasaki.ninja'
                or row.get('source_kind') != 'authored_native_request'):
            return 'unverified', {}
    x = [row['requested_center_xy_m'][0] for row in rows]
    y = [row['requested_center_xy_m'][1] for row in rows]
    speeds = [row['requested_speed_mps'] for row in rows]
    widths = [row['requested_body_width_m'] for row in rows]
    overlap = sum(1 for center, width in zip(y, widths)
                  if center - width / 2 < -3.5 and center + width / 2 > -5.5)
    travel = round(x[-1] - x[0], 4)
    monotonic = all(x[i + 1] > x[i] for i in range(599))
    expected_overlap = (overlap == 0 if witness == 'witness_1' else overlap >= 500)
    complete = (monotonic and travel >= 119 and all(speed == 4.0 for speed in speeds)
                and all(width == .8 for width in widths) and expected_overlap)
    return ('met' if complete else 'not_met'), {
        'joined_frames': 600, 'requested_travel_m': travel,
        'requested_sidewalk_overlap_frames': overlap,
        'monotonic_longitudinal_travel': monotonic,
        'source_kind': 'authored_native_request',
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--witness', choices=('witness_1', 'witness_2'), required=True)
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, default=HERE / 'current-30s-compatibility-manifest.json')
    args = parser.parse_args()
    entry = next(item for item in json.loads(args.manifest.read_text())['cases']
                 if item['case_id'].endswith('__' + args.witness))
    construction = json.loads((HERE / entry['construction']).read_text())
    source = next(item['content'] for item in construction['files'] if item['path'] == 'requested-tracks.jsonl')
    rows = [json.loads(line) for line in source.splitlines()]
    result = {
        'case_id': entry['case_id'], 'construction_sha256': sha(HERE / entry['construction']),
        'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
        'original_native_observed': False, 'city_authority_reviewed': False,
        'legal_verdict': None,
    }
    if args.kind == 'lifecycle':
        assert EVENTS.index('owner_released') < EVENTS.index('saved_processing_started')
        premature = EVENTS[:-2] + list(reversed(EVENTS[-2:]))
        assert premature.index('saved_processing_started') < premature.index('owner_released')
        result.update(events=EVENTS, exit_code=0,
                      negative_premature_saved_processing_rejected=True)
    else:
        if args.kind == 'incomplete_motion':
            for row in rows[6:]:
                row['requested_center_xy_m'] = rows[5]['requested_center_xy_m']
        elif args.kind == 'missing_evidence':
            rows.pop()
        status, measured = evaluate(rows, args.witness)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[args.kind]
        if status != expected:
            raise ValueError(f'{args.kind}: expected {expected}, measured {status}')
        result.update(physical_checks={'maneuver': {
            'status': status,
            'method': '600 ordered 20 Hz authored motorcycle body and speed samples; requested path completion',
            'sources': [entry['construction']],
        }}, maneuver_completed=status == 'met',
            realized_observables=measured if status == 'met' else {},
            requested_track_sha256=hashlib.sha256(source.encode()).hexdigest())
    write(args.output, result)
    print(json.dumps({'witness': args.witness, 'kind': args.kind,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status')}))


if __name__ == '__main__':
    main()
