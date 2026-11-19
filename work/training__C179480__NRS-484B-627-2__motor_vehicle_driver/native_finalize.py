"""Draft source-bound Native finalization for the C179480 primary pair.

This retains measured motion and explicitly withholds physical/legal acceptance.
Selected-case compatibility and independent traffic/exception review are pending.
"""
import argparse
import json
from pathlib import Path
import sys

from native_channels import CHANNELS, channels_for, derive
from saved_analysis import CAMERAS, review, sha256
from source_measurement import load_rows


ASSIGNMENT = 'training__C179480__NRS-484B-627-2__motor_vehicle_driver'
EXPECTED_OVERLAP = {'reference': True, 'contrast': False,
                    'safe_operation_stop': True}


def _native_writer():
    repo = Path(__file__).resolve().parents[2]
    runtime = str(repo/'runtime/pipeline')
    if runtime not in sys.path:
        sys.path.insert(0, runtime)
    from scenario_pipeline.worker_exchange.native_output import write_result
    return write_result


def finalize(attempt, output):
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    config = json.loads((attempt/'config.json').read_text())
    case = config.get('case_suffix')
    if (case not in EXPECTED_OVERLAP
            or config.get('case_id') != ASSIGNMENT+'__'+case
            or config.get('law_id') != 'NRS-484B-627-2'
            or config.get('rate_hz') != 20):
        raise ValueError('Finalizer requires an exact C179480 primary case config')
    names = [entry.get('name') for entry in
             config.get('recording_description', {}).get('channels', [])]
    expected_channels = channels_for(case)
    if set(names) != set(expected_channels) or len(names) != len(expected_channels):
        raise ValueError('Recording description differs from source channels')
    if (attempt/'result.json').exists() or (attempt/'trace.jsonl').exists():
        raise ValueError('Retain prior finalization; use a fresh attempt')
    map_readback = json.loads((attempt/'native-map-readback.json').read_text())
    if map_readback.get('case') != case:
        raise ValueError('Original map readback belongs to another case')
    rows = load_rows(attempt/'native-actors.jsonl', attempt/'video_frames.jsonl')
    mapping = [json.loads(line) for line in
               (attempt/'video_frames.jsonl').read_text().splitlines() if line.strip()]
    if any(row.get('video_frame') != index for index, row in enumerate(rows)):
        raise ValueError('Original actor video-frame identity differs')
    if any(b['frame']-a['frame'] != 1 or
           abs(y['time_s']-x['time_s']-.05) > .001
           for a,b,x,y in zip(rows,rows[1:],mapping,mapping[1:])):
        raise ValueError('Original 20 Hz Native frame continuity differs')
    # Verify all original source hashes and camera decodes before creating any
    # derived Native output. The saved report itself is written only once.
    report = review(attempt, output, write=False)
    if config.get('duration_s') != len(rows)/20:
        raise ValueError('Original source duration differs from config')
    derived = derive(attempt)
    with (attempt/'trace.jsonl').open('x') as stream:
        for actor, frame in zip(rows, mapping):
            trace = {'frame': actor['frame'], 'time_s': frame['time_s'],
                     'position_m': [actor['ego_x_m'], actor['ego_y_m']],
                     'speed_mps': actor['ego_speed_mps'],
                     'speed_provenance': 'original_carla_velocity',
                     'source_actor_sha256': report['source_sha256']['native-actors.jsonl']}
            stream.write(json.dumps(trace, allow_nan=False)+'\n')
    measured = report['measured_values']
    overlap = bool(measured['roadway_lane_overlap_frames'])
    stopped = measured['complete_stop_observed']
    matched = stopped and overlap == EXPECTED_OVERLAP[case]
    hazard = report.get('hazard_observation')
    if case == 'safe_operation_stop' and (
            not hazard or hazard['sample_count'] != len(rows)):
        raise ValueError('Safe-operation original hazard observation absent')
    target = {
        'target': 'sampled complete stop with requested travel-lane footprint overlap',
        'requested': EXPECTED_OVERLAP[case], 'measured': overlap,
        'method': 'original actor velocity/body/lane and synchronized frame map',
        'tolerance': '0.05 m/s engineering stop tolerance; no legal threshold',
        'matched': matched, 'physical_cause_confirmed': False,
        'cause_evidence': ['native-actors.jsonl','video_frames.jsonl',
                           'native-map-readback.json'],
    }
    source_hashes = dict(report['source_sha256'])
    source_hashes['trace.jsonl'] = sha256(attempt/'trace.jsonl')
    sources = {name: source_hashes[name] for name in
               ('native-actors.jsonl','video_frames.jsonl','native-map-readback.json')}
    checks = {name: {'status': 'unverified', 'method': method,
                     'sources': sources, 'intervals': [],
                     'legal_verdict_claimed': False,
                     'physical_causation_claimed': False}
              for name, method in (
                  ('setup','independent roadway/map and camera visibility review'),
                  ('target','original sampled stop and lane-footprint review'),
                  ('maneuver','independent normal-and-reasonable traffic effect and exception review'))}
    checks['target']['status'] = 'met' if matched else 'not_met'
    result = {
        'case_id': config['case_id'],
        'measured_values': measured,
        'target_checks': [target],
        'setup_confirmed': False,
        'behavior_attempted': True,
        'maneuver_completed': False,
        'physical_checks': checks,
        'termination_reason': 'full original attempt retained',
        'physical_failure_flags': ['traffic_impediment_and_exceptions_unreviewed']+
                                  (['safe_operation_necessity_unreviewed']
                                   if case == 'safe_operation_stop' else [])+
                                  ([] if matched else ['sampled_stop_target_not_met']),
        'trace_reference': 'trace.jsonl',
        'video_references': [name+'.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': [
            {'name': entry['name'], 'unit': entry['unit'],
             'reference': 'channels/'+entry['name']+'.jsonl'}
            for entry in config['recording_description']['channels']],
        'realized_observables': {
            'sampled_roadway_lane_overlap': {
                'value': overlap, 'unit': 'bool',
                'method': 'source-joined stopped actor body and driving-lane readback',
                'reference': 'native-actors.jsonl'},
            'traffic_effect_evidence': {
                'value': {
                    'following_initial_speed_mps': measured['following_initial_speed_mps'],
                    'following_min_speed_mps': measured['following_min_speed_mps'],
                    'following_speed_drop_mps': measured['following_speed_drop_mps'],
                    'following_min_gap_m': measured['following_min_gap_m'],
                    'normal_reasonable_movement_impeded':
                        'independent_original_source_review_required'},
                'unit': 'structured',
                'method': 'source-joined original ego/follower actor and frame rows',
                'reference': 'channels/traffic_effect_evidence.jsonl'}},
        'provenance_kind': 'native',
        'accepted': False, 'legal_verdict_claimed': False,
    }
    if hazard is not None:
        result['realized_observables']['source_visible_hazard'] = {
            'value': hazard, 'unit': 'structured',
            'method': 'original actor body, lane, velocity and gap rows',
            'reference': 'native-actors.jsonl'}
    _native_writer()(attempt, result)
    report['derived_channels'] = derived
    report['trace_sha256'] = source_hashes['trace.jsonl']
    report['native_result_sha256'] = sha256(attempt/'result.json')
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)


if __name__ == '__main__':
    main()
