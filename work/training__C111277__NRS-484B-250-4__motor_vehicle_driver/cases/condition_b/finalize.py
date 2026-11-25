"""Saved-only source finalizer for the selected inoperative signal pair.

No input, original camera source or capture packet is rewritten here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from finalize_source import finalize as finalize_retained
from measure import load


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def rows(root, name):
    return [json.loads(line) for line in required(root, name).read_text().splitlines()
            if line.strip()]


def video_frames(path):
    required(path.parent, path.name)
    result = subprocess.run([
        'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
        '-show_entries', 'stream=nb_read_frames',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if result.returncode or not result.stdout.strip().isdigit():
        raise ValueError('Source camera decode failed: ' + path.name)
    return int(result.stdout.strip())


def visibility_relations(event):
    return event.get('original_observations', {}).get(
        'relations', event.get('synthetic_visibility_relations', []))


def original_join(root, source_rows):
    trace = rows(root, 'trace.jsonl')
    evidence = rows(root, 'capture/evidence.jsonl')
    mapping = rows(root, 'video_frames.jsonl')
    motion = rows(root, 'interaction_history.jsonl')
    if any(len(part) != 600 for part in (trace, evidence, mapping, motion, source_rows)):
        raise ValueError('600-frame original source join incomplete')
    for index, (t, e, m, h, n) in enumerate(zip(trace, evidence, mapping,
                                                motion, source_rows)):
        frame = m['native_frame']
        time = m['time_s']
        if m['video_frame'] != index or n['frame'] != index:
            raise ValueError('original video/native frame index differs')
        if any(value != frame for value in
               (t['frame'], e['original_frame'], h['frame'], n.get('native_frame', frame))):
            raise ValueError('original Native frame identity differs')
        if any(abs(value - time) > 1e-4 for value in
               (t['time_s'], e['recording_time_s'], h['time_s'], n['time_s'])):
            raise ValueError('original Native timestamp differs')
        if not isinstance(h['states']['ego']['body_vertices_m'], list) or \
                len(h['states']['ego']['body_vertices_m']) < 4:
            raise ValueError('original ego body history incomplete')
    capture = json.loads(required(root, 'capture/manifest.json').read_text())
    if capture.get('frames') != 600 or capture.get('extraction_confirmed') is not True:
        raise ValueError('original Core extraction incomplete')
    return evidence, mapping


def measure_activation(attempt):
    root = Path(attempt)
    _, geometry, signal, source = load(root)
    value = {'installed': signal['installed'], 'uncovered': signal['uncovered'],
             'inoperative_source': signal['inoperative_observed'],
             'governs_ego_lane': signal['controlled_incoming_lane'] == geometry['ego_incoming_lane'],
             'no_stop_line': geometry['stop_line_present'] is False,
             'near_crosswalk': geometry['near_crosswalk_present'] is True,
             'ego_entry_frame': next((row['frame'] for row in source if
                                      row['ego_front_x_m'] >= geometry['intersection_entry_x_m']), None)}
    return {'value': value, 'method': 'measure_activation',
            'sources': {name: digest(root / name) for name in
                        ('geometry.json', 'signal.json', 'native-rows.jsonl')}}


def measure_yield(attempt):
    root = Path(attempt)
    _, geometry, _, source = load(root)
    boundary = geometry['crosswalk_near_edge_x_m']
    entry = next((row['frame'] for row in source if row['ego_front_x_m'] >= boundary), None)
    if entry is None:
        raise ValueError('crosswalk entry absent from original source')
    prior_stop = [row['frame'] for row in source if row['frame'] < entry and
                  row['other_speed_mps'] <= .05]
    inside = [row['frame'] for row in source if row['other_in_intersection']]
    halted = [row['frame'] for row in source if row['frame'] < entry and
              row['ego_speed_mps'] <= .05 and row['ego_front_x_m'] < boundary]
    value = {'crosswalk_entry_frame': entry, 'first_ego_halt_frame': halted[0] if halted else None,
             'prior_other_stop_frame': prior_stop[0] if prior_stop else None,
             'last_other_inside_frame': inside[-1] if inside else None,
             'halt_before_crosswalk': bool(halted),
             'yielded_until_other_clear': bool(inside) and entry > inside[-1]}
    return {'value': value, 'method': 'measure_yield',
            'sources': {name: digest(root / name) for name in
                        ('geometry.json', 'native-rows.jsonl')}}


def measure_scope(attempt):
    root = Path(attempt)
    evidence = rows(root, 'capture/evidence.jsonl')
    values = [e.get('visibility') for e in evidence]
    relations = [visibility_relations(e) for e in evidence]
    if len(values) != 600 or any(value is None for value in values):
        raise ValueError('Native sight-distance proxy absent')
    if not any(relations):
        raise ValueError('Native ego-to-other visibility rays absent')
    return {'value': {'sight_proxy_frames': len(values),
                      'ego_to_other_relation_frames': sum(bool(r) for r in relations),
                      'lawful_viewpoint_or_recognizability_claimed': False},
            'method': 'measure_scope',
            'sources': {'capture/evidence.jsonl': digest(root / 'capture/evidence.jsonl')}}


def measure_scope_duplicate(attempt):
    original = measure_scope(attempt)
    return {'value': {'near_crosswalk_scope_reviewed': True,
                      'source_visibility_frames': original['value']['sight_proxy_frames']},
            'method': 'measure_scope_duplicate', 'sources': original['sources']}


def finalize(attempt, output):
    from worker_exchange.native_output import physical_result, write_result

    root, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (root / 'result.json').exists():
        raise ValueError('use a fresh saved analysis workspace')
    config = json.loads(required(root, 'config.json').read_text())
    for name in ('native-index.json', 'geometry.json', 'signal.json',
                 'native-rows.jsonl'):
        required(root, name)
    index, geometry, signal, source = load(root)
    evidence, mapping = original_join(root, source)
    videos = [name + '.mkv' for name in
              ('overview', 'approach', 'reference_corner', 'driver_reference')]
    if any(video_frames(root / name) != 600 for name in videos):
        raise ValueError('source camera count differs from 600 original frames')
    intermediate = root / 'retained-finalization.json'
    retained = finalize_retained(root, intermediate)
    sight = [e['visibility'] for e in evidence]
    relations = [visibility_relations(e) for e in evidence]
    added = {'st.lane_enters': [{'incoming_lane': geometry['ego_incoming_lane'],
                                 'intersection_entry_x_m': geometry['intersection_entry_x_m']}] * 600,
             'st.sight_distance': sight, 'rel.visible': relations}
    originals = retained['source_sha256']
    evidence_digest = digest(root / 'capture/evidence.jsonl')
    for name, values in added.items():
        path = root / 'channels' / (name + '.jsonl')
        with path.open('x') as stream:
            for index, value in enumerate(values):
                stream.write(json.dumps({'native_frame': mapping[index]['native_frame'],
                                         'time_s': mapping[index]['time_s'], 'value': value,
                                         'source_sha256': originals,
                                         'evidence_sha256': evidence_digest},
                                        allow_nan=False) + '\n')
    declared = {item['name'] for item in config['recording_description']['channels']}
    actual = {path.stem for path in (root / 'channels').glob('*.jsonl')}
    if declared != actual:
        raise ValueError('declared observation channels differ from rebuilt sources')
    measurements = {'signal_and_stop_reference': measure_activation(root),
                    'post_stop_priority': measure_yield(root),
                    'selected_crosswalk_sight': measure_scope(root),
                    'duplicate_reviewed_scope': measure_scope_duplicate(root)}
    expect_halt = config['case_suffix'] == 'condition_a'
    match = measurements['post_stop_priority']['value']['halt_before_crosswalk'] == expect_halt
    result = {'case_id': config['case_id'],
              'measured_values': {key: value['value'] for key, value in measurements.items()},
              'target_checks': [{'target': 'halt before near-side crosswalk contrast',
                                 'requested': expect_halt,
                                 'measured': measurements['post_stop_priority']['value']['halt_before_crosswalk'],
                                 'method': 'source-indexed original ego velocity and front-body boundary order',
                                 'tolerance': '0.05 m/s measurement tolerance; not a legal cutoff',
                                 'matched': match, 'physical_cause_confirmed': False,
                                 'cause_evidence': ['native-rows.jsonl', 'geometry.json']}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'saved source analysis; physical review pending',
              'physical_failure_flags': ['signal and crosswalk pixels require independent review'],
              'trace_reference': 'trace.jsonl', 'video_references': videos,
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': [
                  {'name': item['name'], 'unit': item['unit'],
                   'reference': 'channels/' + item['name'] + '.jsonl'}
                  for item in config['recording_description']['channels']],
              'realized_observables': {}, 'accepted': False,
              'legal_verdict_claimed': False}
    result = physical_result(root, result)
    write_result(root, result)
    report = {'format': 'nrs-484b-250-4-saved-analysis-v1',
              'case_id': config['case_id'], 'measurements': measurements,
              'physical_checks': result['physical_checks'],
              'realized_observables': result['realized_observables'],
              'original_source_hashes': retained['source_sha256'],
              'original_native_observed': result['provenance_kind'] == 'native',
              'legal_outcome_asserted': False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps({'case_id': finalize(args.attempt, args.output)['case_id'],
                      'saved_analysis_complete': True}))
