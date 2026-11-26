"""Saved-only source-joined contest-aid observations without legal judgment."""
import argparse
import hashlib
import json
from pathlib import Path

from contest_aid import CASES, measure_original
from package_spec import CAMERA_NAMES


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def source_sealed_contest_measurement(value):
    return value


def analyze(attempt):
    root = Path(attempt).resolve()
    config = json.loads(required(root, 'config.json').read_text())
    case_id = config['selected_case_id']
    case = next((item for item in CASES if case_id.endswith('__' + item.name)), None)
    need(case is not None and config['case']['case_id'] == case_id,
         'exact aid case differs')
    packet_path = required(root, 'contest-packet.json')
    receipt = json.loads(required(root, 'original-source-receipt.json').read_text())
    diagnostic = receipt.get('diagnostic_fixture') is True
    expected_kind = 'synthetic_diagnostic_fixture' if diagnostic else 'original_native_capture'
    need(receipt.get('source_kind') == expected_kind and
         receipt.get('case_id') == case_id and
         receipt.get('packet_sha256') == sha(packet_path),
         'original contest source receipt differs')
    packet = json.loads(packet_path.read_text())
    need(packet.get('assignment_id') == config['assignment_id'] and
         packet.get('case_id') == case_id and isinstance(packet.get('scene'), dict),
         'exact source identities differ')
    trace_path = required(root, 'trace.jsonl')
    frame_path = required(root, 'video_frames.jsonl')
    need(receipt.get('trace_sha256') == sha(trace_path) and
         receipt.get('frame_map_sha256') == sha(frame_path),
         'original trace or frame map differs')
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
    frame_map = [json.loads(line) for line in frame_path.read_text().splitlines()]
    rows = packet['frames']
    expected_frames = 9 if diagnostic else 900
    need(len(rows) == len(trace) == len(frame_map) == expected_frames,
         'required original source frame count differs')
    for index, (row, motion, mapped) in enumerate(zip(rows, trace, frame_map)):
        need(row.get('original_frame') == mapped.get('video_frame') == index and
             row.get('native_frame') == motion.get('frame') ==
             mapped.get('native_frame') == mapped.get('carla_frame') and
             row.get('native_time_s') == motion.get('time_s') == mapped.get('time_s'),
             'original Native frame/time join differs')
    measured = measure_original(rows, packet['scene'], case,
                                expected_frames=expected_frames)
    scene = packet['scene']
    values = {
        'participants': {name: scene[name] for name in
                         ('ego_person_id', 'other_person_id', 'ego_vehicle_id', 'other_vehicle_id')},
        'highway_jurisdiction': {'highway': case.highway,
                                 'municipal_jurisdiction': scene['municipal_jurisdiction'],
                                 'highway_source_sha256': scene['highway_status_source_sha256']},
        'lane_and_route': {'lane_marking_xy': scene['lane_marking_xy'],
                           'ego_route_xy': scene['ego_route_xy'],
                           'other_route_xy': scene['other_route_xy']},
        'cue_and_episode': {'cue_frame': measured['cue_frame'],
                            'other_motion_first_frame': measured['other_motion_first_frame'],
                            'candidate_contest': case.candidate_contest,
                            'contest_judgment': None, 'aid_abet_judgment': None},
        'two_vehicle_motion': {'max_ego_speed_mps': measured['max_ego_speed_mps'],
                                'max_other_speed_mps': measured['max_other_speed_mps'],
                                'frame_count': expected_frames},
        'camera_frame_identity': {'frame_count': expected_frames,
                                  'first_native_frame': frame_map[0]['native_frame'],
                                  'last_native_frame': frame_map[-1]['native_frame']}}
    source_hashes = {name: sha(required(root, name)) for name in
                     ('contest-packet.json', 'original-source-receipt.json',
                      'trace.jsonl', 'video_frames.jsonl')}
    measurements = {name: {'method': 'source_sealed_contest_measurement',
                           'value': source_sealed_contest_measurement(value),
                           'sources': source_hashes}
                    for name, value in values.items()}
    evidence = []
    for channel in config['case']['recording_description']['channels']:
        name = channel['name']
        target = root / ('channel-' + name + '.jsonl')
        content = ''.join(json.dumps({'time_s': row['time_s'],
                                      'value': row['native_frame'] if name == 'camera_frame_identity'
                                      else [row['ego_xy'], row['other_xy']] if name == 'two_vehicle_motion'
                                      else row['cue_observed'] if name == 'cue_and_episode'
                                      else values[name]}, sort_keys=True) + '\n'
                          for row in rows)
        if target.exists():
            need(target.read_text() == content, 'derived channel differs from saved source')
        else:
            target.write_text(content)
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': target.name})
    context = root / 'channel-reviewed_native_site.json'
    content = json.dumps({'reviewed_native_site': {
        'site_sha256': packet['reviewed_site_sha256'],
        'highway_source_sha256': scene['highway_status_source_sha256'],
        'contest_episode_source_sha256': scene['contest_episode_source_sha256']}},
        sort_keys=True) + '\n'
    if context.exists():
        need(context.read_text() == content, 'reviewed site context differs')
    else:
        context.write_text(content)
    evidence.append({'name': 'reviewed_native_site', 'unit': 'source record',
                     'reference': context.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {'case_id': case_id, 'measured_values': values,
              'target_checks': [{'target': 'source-bound two-vehicle cue and motion',
                                 'requested': case.name, 'measured': case.name,
                                 'method': 'original two-vehicle and cue readback',
                                 'tolerance': 0, 'matched': True,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': source_hashes}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'saved physical and legal review pending',
              'physical_failure_flags': ['physical_acceptance_unverified'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERA_NAMES],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['case']['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'diagnostic_fixture': diagnostic,
              'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False}
    result = physical_result(root, result)
    write_result(root, result)
    return {'format': 'worker-analysis-report', 'case_id': case_id,
            'analysis_complete': True, 'diagnostic_fixture': diagnostic,
            'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False, 'measurements': measurements,
            'physical_checks': result['physical_checks'],
            'realized_observables': result['realized_observables'],
            'limitations': ['Cue and motion do not decide contest, aid or abet.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n')
