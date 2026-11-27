"""Saved-only subsection 2 observations; no CARLA import or legal conclusion."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from stop_yield_saved_measure import measure_paths
from worker_exchange.native_output import physical_result, write_result

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
COUNT = 600


def required(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(root, name):
    return [json.loads(row) for row in required(root, name).read_text().splitlines() if row.strip()]


def verify_source_joins(root, packet, observed):
    frames = packet['frames']
    video = lines(root, 'video_frames.jsonl')
    trace = lines(root, 'trace.jsonl')
    if len(frames) != COUNT or len(video) != COUNT or len(trace) != COUNT:
        raise ValueError('Missing complete 600-frame saved source join')
    for i, (sample, image, core) in enumerate(zip(frames, video, trace)):
        native = sample.get('native_frame')
        if (sample.get('frame') != i or image.get('video_frame') != i or
                image.get('carla_frame') != native or core.get('frame') != native or
                abs(sample.get('t_s', -100) - image.get('time_s', -200)) > 1e-6 or
                abs(sample.get('t_s', -100) - core.get('time_s', -300)) > 1e-6 or
                image.get('source_cameras') != sample.get('source_cameras') or
                set(image.get('source_cameras', {})) != set(CAMERAS)):
            raise ValueError('Original Core/body/video frame join differs')
        if observed['source_kind'] == 'native_saved_sample':
            hashes = image.get('camera_rgb_sha256')
            if not isinstance(hashes, dict) or set(hashes) != set(CAMERAS) or any(
                    not isinstance(value, str) or len(value) != 64 for value in hashes.values()):
                raise ValueError('Original camera RGB hash missing')
            for body_name in ('subject_body_vertices_m', 'counterpart_body_vertices_m'):
                if len(sample.get(body_name, [])) < 4:
                    raise ValueError('Original participant body geometry missing: ' + body_name)
    if observed['source_kind'] == 'native_saved_sample':
        provenance = json.loads(required(root, 'acquisition-provenance.json').read_text())
        if (provenance.get('provenance_kind') != 'native' or not provenance.get('native_executed') or
                provenance.get('diagnostic_fixture') or provenance.get('physical_acceptance_claimed')):
            raise ValueError('Original Native provenance missing')
        evidence = lines(root, 'capture/evidence.jsonl')
        if len(evidence) != COUNT or any(evidence[i].get('original_frame') != frames[i]['native_frame']
                                         for i in range(COUNT)):
            raise ValueError('Original Native evidence frame join differs')
        controls = json.loads(required(root, 'entrance_controls.json').read_text())
        if controls.get('map_readback_sha256') != sha(required(root, 'road.xodr')):
            raise ValueError('Original map/control hash differs')
        if controls.get('stop_reference') == 'nearest_viewpoint':
            rays = json.loads(required(root, 'viewpoint_sight_rays.json').read_text())
            if (len(rays) != COUNT or controls.get('viewpoint_sight_rays_sha256') !=
                    sha(required(root, 'viewpoint_sight_rays.json')) or
                    any(rays[i].get('native_frame') != frames[i]['native_frame'] or
                        len(rays[i].get('rays', [])) != 18 for i in range(COUNT))):
                raise ValueError('Original nearest-viewpoint rays missing or stale')
        if controls.get('control_exception') is not None:
            states = json.loads(required(root, 'control_state_frames.json').read_text())
            if (len(states) != COUNT or controls.get('control_state_frames_sha256') !=
                    sha(required(root, 'control_state_frames.json')) or
                    any(states[i].get('native_frame') != frames[i]['native_frame']
                        for i in range(COUNT))):
                raise ValueError('Original control state missing or stale')
    for name in CAMERAS:
        path = required(root, name + '.mkv')
        count = subprocess.check_output([
            'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
            '-show_entries', 'stream=nb_read_frames', '-of', 'default=nokey=1:noprint_wrappers=1',
            str(path)], text=True, timeout=120).strip()
        if count != str(COUNT):
            raise ValueError('Source camera decoded frame count differs: ' + name)


def measure_pre_entry(observed):
    return {'near_zero_frames': observed['pre_entry_near_zero_frames_before_reference'],
            'subject_control': observed['subject_control'],
            'stop_reference': observed['stop_reference']}


def measure_counterpart(observed):
    return {'inside_at_entry': observed['counterpart_inside_at_entry'],
            'inside_during_frames': observed['counterpart_inside_during_crossing_frames'],
            'approach_ttc_min_s': observed['counterpart_approach_ttc_min_s'],
            'not_obligated': observed['counterpart_not_obligated_to_stop_or_yield']}


def finalize(attempt, output):
    root = Path(attempt).resolve()
    target = Path(output)
    if target.exists():
        raise ValueError('Retain prior saved analysis output')
    config = json.loads(required(root, 'config.json').read_text())
    case = config['selected_case_id']
    packet_path = required(root, 'nonthrough_saved_packet.json')
    controls_path = required(root, 'entrance_controls.json')
    observed = measure_paths(packet_path, controls_path)
    packet = json.loads(packet_path.read_text())
    verify_source_joins(root, packet, observed)
    channel = root / 'channels'
    channel.mkdir(exist_ok=True)
    def stream(name, value):
        (channel / (name + '.jsonl')).write_text(''.join(
            json.dumps({'time_s': row['t_s'], 'value': value(row)}, allow_nan=False) + '\n'
            for row in packet['frames']))

    stream('subject_counterpart_crossing_trace', lambda row: {
            'subject_speed_mps': row['subject_speed_mps'],
            'counterpart_speed_mps': row['counterpart_speed_mps'],
            'subject_inside': row['subject_inside'],
            'counterpart_inside': row['counterpart_inside'],
            'counterpart_distance_to_conflict_m': row['counterpart_distance_to_conflict_m']})
    stream('all_entrance_controls', lambda row: observed['all_entrance_controls'])
    stream('stopping_reference_hierarchy', lambda row: {
        'reference': observed['stop_reference'],
        'subject_front_before_reference': row['subject_front_before_reference'],
        'subject_body_vertices_m': row['subject_body_vertices_m']})
    stream('original_control_state', lambda row: {
        'officer_controlling': row['officer_controlling'],
        'signal_controlling': row['signal_controlling'],
        'direction_legally_unassessed': row['control_direction_legally_unassessed']})
    stream('ego_pose', lambda row: {
        'body_vertices_m': row['subject_body_vertices_m'],
        'speed_mps': row['subject_speed_mps']})
    contexts = {
        'context_subject_counterpart_crossing_trace': {
            'subject_id': packet['subject_id'], 'counterpart_id': packet['counterpart_id'],
            'source_sha256': sha(packet_path)},
        'context_all_entrance_controls': {
            'entrance_controls': observed['all_entrance_controls'],
            'source_sha256': sha(controls_path)},
        'context_stopping_reference_hierarchy': {
            'stop_reference': observed['stop_reference'],
            'source_sha256': sha(controls_path)},
        'context_original_control_state': {
            'control_exception': json.loads(controls_path.read_text())['control_exception'],
            'source_sha256': sha(packet_path)}}
    for name, value in contexts.items():
        (channel / (name + '.json')).write_text(json.dumps({name: value}, allow_nan=False) + '\n')
    (root / 'interaction_history.jsonl').write_text(''.join(
        json.dumps({'frame': row['native_frame'], 'time_s': row['t_s'],
                    'ego': {'body_vertices_m': row['subject_body_vertices_m']},
                    'counterpart': {'body_vertices_m': row['counterpart_body_vertices_m']}},
                   allow_nan=False) + '\n' for row in packet['frames']))
    (root / 'control_context.json').write_text(json.dumps({
        'intersection_xy_m': [[-3.5, -3.5], [3.5, -3.5], [3.5, 3.5], [-3.5, 3.5]],
        'authored_geometry_source_sha256': sha(required(root, 'road.xodr')),
        'control_inventory_source_sha256': sha(controls_path),
        'interpretation': 'engineering intersection footprint; not legal stop or hazard threshold'},
        allow_nan=False) + '\n')
    measurements = {
        'pre_entry_stop_or_slow': {'method': 'measure_pre_entry',
            'value': measure_pre_entry(observed),
            'sources': {'nonthrough_saved_packet.json': sha(packet_path),
                        'entrance_controls.json': sha(controls_path)}},
        'counterpart_crossing_and_approach': {'method': 'measure_counterpart',
            'value': measure_counterpart(observed),
            'sources': {'nonthrough_saved_packet.json': sha(packet_path),
                        'entrance_controls.json': sha(controls_path)}}}
    result = {'case_id': case, 'measured_values': observed,
              'target_checks': [{'target': 'requested stop or yield before entry',
                                 'requested': True,
                                 'measured': bool(observed['pre_entry_near_zero_frames_before_reference']),
                                 'method': 'saved original motion and reference geometry',
                                 'tolerance': '0.1 m/s is diagnostic only, not a legal threshold',
                                 'matched': bool(observed['pre_entry_near_zero_frames_before_reference']),
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': ['nonthrough_saved_packet.json', 'entrance_controls.json']}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': '600 saved source frames measured; physical and legal review pending',
              'physical_failure_flags': ['original physical success not independently confirmed'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': [
                  {'name': item['name'], 'unit': item['unit'],
                   'reference': 'channels/' + item['name'] + '.jsonl'}
                  for item in config['recording_description']['channels']
              ] + [
                  {'name': item['name'], 'unit': item['unit'],
                   'reference': 'channels/' + item['name'] + '.json'}
                  for item in config['recording_description']['context_inputs']
              ],
              'realized_observables': {},
              'provenance_kind': 'native' if observed['source_kind'] == 'native_saved_sample' else 'synthetic_fixture',
              'diagnostic_fixture': observed['source_kind'] != 'native_saved_sample',
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    result = physical_result(root, result)
    write_result(root, result)
    report = {'format': 'nrs-484b-257-2-selected-analysis-v1', 'case_id': case,
              'measurements': measurements, 'analysis_complete': True,
              'source_kind': observed['source_kind'], 'physical_acceptance_claimed': False,
              'limitations': ['Original road/sign/control review and legal caution/hazard/yield judgments remain.']}
    target.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), allow_nan=False))
