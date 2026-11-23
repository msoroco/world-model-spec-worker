"""Source-bound saved analysis for the C10389 stop-device comparison.

The synthetic switch is only for CPU diagnostics. Runtime process-saved never
passes it, so production analysis requires original Native sources and all five
fully decoded videos. Neither path decides official placement or legal obedience.
"""
import argparse
import hashlib
import json
from pathlib import Path

from saved import prepare, measure

VIEWS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
         'driver_reference.mkv', 'raw.mkv')
SOURCES = ('native-map-readback.json', 'native-raw-actors.jsonl',
           'video_frames.jsonl', 'frame-review.jsonl',
           'native-capture-report.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def analyze(attempt, output, synthetic_cpu=False):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Use a fresh saved analysis directory')
    map_source = json.loads(required(attempt, 'native-map-readback.json').read_text())
    expected_kind = 'synthetic_cpu' if synthetic_cpu else 'original_native'
    if map_source.get('source_kind') != expected_kind:
        raise ValueError('Native source kind differs from analysis mode')
    if not synthetic_cpu:
        for name in VIEWS:
            required(attempt, name)
        if not (attempt / 'trace.jsonl').is_file():
            raise ValueError('Missing required source: trace.jsonl')
    for name in SOURCES:
        required(attempt, name)
    derived = attempt / 'device-derived'
    receipt = prepare(attempt, attempt, derived, synthetic=synthetic_cpu)
    measured = measure(attempt, derived)
    if measured['source_kind'] != expected_kind or receipt['source_kind'] != expected_kind:
        raise ValueError('Prepared source kind differs')
    cfg = json.loads(required(attempt, 'config.json').read_text())
    requested_obey = cfg['requested_obey']
    stop_frames = measured['stopped_before_device_frames']
    crossing_frames = measured['front_body_at_device_station_frames']
    target_matched = stop_frames >= 20 if requested_obey else crossing_frames > 0 and stop_frames == 0
    hashes = {name: sha(required(attempt, name)) for name in SOURCES}
    analysis = {
        'format': 'worker-analysis-report', 'case_id': cfg['case_id'],
        'candidate_id': cfg['candidate_id'], 'analysis_complete': True,
        'provenance_kind': 'synthetic_fixture' if synthetic_cpu else 'native_source_shape_unverified',
        'diagnostic_fixture': synthetic_cpu,
        'measurements': {'stop_before_device_frames': stop_frames,
                         'body_at_device_station_frames': crossing_frames,
                         'first_body_at_device_station_frame': measured['first_body_at_device_station_frame'],
                         'reviewed_visible_device_face_frames': measured['reviewed_visible_device_face_frames'],
                         'reviewed_visible_approach_area_frames': measured['reviewed_visible_approach_area_frames']},
        'source_hashes': hashes,
        'media_hashes': receipt['media_hashes'],
        'limitations': ['Authored OpenDRIVE landmark does not establish official placement',
                        'Police direction and NRS 484B.307 exception remain unreviewed',
                        'No legal verdict or physical acceptance is claimed']}
    result = {
        'case_id': cfg['case_id'],
        'measured_values': analysis['measurements'],
        'target_checks': [{'target': 'authored stop-device approach response',
                           'requested': 'stop before device' if requested_obey else 'pass device',
                           'measured': {'stopped_frames': stop_frames, 'crossing_frames': crossing_frames},
                           'method': '600 joined Native body/velocity rows and analytic device station',
                           'tolerance': '20 frames at 20 Hz for authored stop request; no legal threshold',
                           'matched': target_matched, 'physical_cause_confirmed': False,
                           'cause_evidence': list(SOURCES)}],
        'setup_confirmed': False,
        'behavior_attempted': not synthetic_cpu,
        'maneuver_completed': bool(not synthetic_cpu and target_matched),
        'termination_reason': '600 retained source frames analyzed',
        'physical_failure_flags': ['official_placement_unverified',
                                   'police_direction_unverified',
                                   'signal_exception_unreviewed',
                                   'original_pixels_unreviewed'],
        'trace_reference': 'trace.jsonl',
        'video_references': list(VIEWS),
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': cfg.get('recording_description', {}),
        'recording_evidence': [{'name': name, 'unit': 'source', 'reference': name}
                               for name in SOURCES],
        'realized_observables': {'authored_device_response': {
            'value': analysis['measurements'], 'unit': 'frames',
            'method': 'source-bound body and velocity measurement',
            'time_window': '600 frames at 20 Hz', 'statistic': 'count',
            'reference': 'native-raw-actors.jsonl'}},
        'provenance_kind': analysis['provenance_kind'],
        'diagnostic_fixture': synthetic_cpu,
        'accepted': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result, physical_result
    if not synthetic_cpu:
        result = physical_result(attempt, result)
    validate_result(result)
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + '\n')
    (attempt / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return analysis


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--synthetic-cpu', action='store_true')
    args = parser.parse_args()
    print(json.dumps(analyze(args.attempt, args.output, args.synthetic_cpu), allow_nan=False))
