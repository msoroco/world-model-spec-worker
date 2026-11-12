"""CPU protocol for motion and lifecycle outcomes; synthetic sources only."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREFIX = HERE.name + '__'
SUFFIXES = ('baseline_right', 'baseline_left', 'passing_left', 'closure_left',
            'three_lane_left', 'one_way_left', 'narrow_left')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def source_rows(text):
    return [json.loads(line) for line in text.splitlines() if line]


def evaluate(case, kind):
    suffix = case.removeprefix(PREFIX)
    if case != PREFIX + suffix or suffix not in SUFFIXES:
        raise ValueError('Unknown exact physical fixture case')
    if kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown physical fixture kind')
    diagnostic_path = HERE / ('diagnostic-' + suffix + '.json')
    audit_path = HERE / (suffix.replace('_', '-') + '-delivery-proof.json')
    if suffix == 'baseline_right':
        audit_path = HERE / 'baseline-right-delivery-proof.json'
    elif suffix == 'baseline_left':
        audit_path = HERE / 'baseline-left-delivery-proof.json'
    elif suffix == 'passing_left':
        audit_path = HERE / 'passing-left-delivery-proof.json'
    elif suffix == 'closure_left':
        audit_path = HERE / 'closure-left-delivery-proof.json'
    elif suffix == 'three_lane_left':
        audit_path = HERE / 'three-lane-left-delivery-proof.json'
    elif suffix == 'one_way_left':
        audit_path = HERE / 'one-way-left-delivery-proof.json'
    elif suffix == 'narrow_left':
        audit_path = HERE / 'narrow-left-delivery-proof.json'
    diagnostic = json.loads(diagnostic_path.read_text())
    audit = json.loads(audit_path.read_text())
    if audit.get('case_id') != case or not audit.get('analysis_recomputed') or not audit.get('four_camera_full_decode'):
        raise ValueError('Exact diagnostic source audit unavailable')
    files = diagnostic['files']
    required = ('ego_road_frames.jsonl', 'trace.jsonl', 'video_frames.jsonl', 'road_exception_context.json')
    if any(name not in files for name in required):
        raise ValueError('Diagnostic fixture lacks original road/trace/frame/context source')
    road, trace, frame_map = (source_rows(files[name]) for name in required[:3])
    if len(diagnostic['videos']) != 4 or {v['path'] for v in diagnostic['videos']} != {
            'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'}:
        raise ValueError('Physical protocol requires four original camera specifications')
    if not 3 <= len(road) == len(trace) == len(frame_map):
        raise ValueError('Physical protocol original frame count differs')
    if any((r['frame'], r['time_s']) != (t['frame'], t['time_s']) or
           (r['frame'], r['time_s']) != (v['native_frame'], v['time_s'])
           for r, t, v in zip(road, trace, frame_map)):
        raise ValueError('Physical protocol source frame join differs')
    first, last = trace[0]['position_m'], trace[-1]['position_m']
    progress = ((last[0] - first[0]) ** 2 + (last[1] - first[1]) ** 2) ** .5
    if kind == 'incomplete_motion':
        progress = 0.0  # Explicit synthetic stalled-controller fixture.
    if kind == 'missing_evidence':
        observed = None  # Explicit synthetic missing road/body stream fixture.
    else:
        observed = audit.get('body_side_observed')
    if observed is None:
        status = 'unverified'
    elif progress > 1.0:
        status = 'met'
    else:
        status = 'not_met'
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if status != expected:
        raise ValueError('Physical fixture classified ' + status + ', expected ' + expected)
    sources = {'diagnostic': diagnostic_path.name, 'diagnostic_sha256': sha(diagnostic_path),
               'original_source_audit': audit_path.name, 'original_source_audit_sha256': sha(audit_path),
               'fixture_mutation': kind}
    return {'case_id': case, 'fixture_kind': kind, 'fixture_only': True,
            'diagnostic_fixture': True, 'actual_native_capture': False,
            'physical_checks': {'maneuver': {'status': status,
                'method': 'joined Native-shaped original road/trace/frame sources, source audit and explicit synthetic outcome mutation',
                'sources': sources, 'missing_evidence': ['ego_road_frames.jsonl'] if observed is None else []}},
            'maneuver_completed': status == 'met',
            'realized_observables': {'diagnostic_route_progress_m': progress,
                                     'diagnostic_body_side': observed,
                                     'diagnostic_source_frames': len(road)} if status == 'met' else {},
            'provenance_kind': 'native',
            'provenance_note': 'Native-shaped synthetic source protocol only; no actual CARLA capture or pixel review',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def lifecycle(out_of_order=False):
    events = EVENTS.copy()
    if out_of_order:
        events[-2:] = events[-2:][::-1]
    if events != EVENTS:
        raise ValueError('Saved processing precedes Native ownership closure')
    return {'events': events, 'fixture_only': True, 'actual_native_capture': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case')
    parser.add_argument('--kind')
    parser.add_argument('--output')
    parser.add_argument('--lifecycle', action='store_true')
    parser.add_argument('--out-of-order', action='store_true')
    args = parser.parse_args()
    result = lifecycle(args.out_of_order) if args.lifecycle else evaluate(args.case, args.kind)
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
