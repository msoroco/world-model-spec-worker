"""Saved-only original green exhibition measurement and Native result projection."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from native_scene import source
from saved_attempt import process_saved

REQUIRED = ('original-green-packet.json', 'site.json', 'original-events.json',
            'video_frames.jsonl')


def verified(attempt, name):
    path = attempt / name
    acquisition = json.loads((attempt / 'acquisition.json').read_text())
    item = acquisition.get(name)
    if not path.is_file() or not isinstance(item, dict) or item.get('kind') != 'original_native':
        raise ValueError('Missing required source: ' + name)
    if hashlib.sha256(path.read_bytes()).hexdigest() != item.get('sha256'):
        raise ValueError('stale original Native source: ' + name)
    return path


def measure_green(attempt):
    attempt = Path(attempt)
    for name in REQUIRED:
        verified(attempt, name)
    packet = json.loads(verified(attempt, 'original-green-packet.json').read_text())
    if packet.get('site_ref') != {'path': 'site.json',
           'sha256': hashlib.sha256((attempt / 'site.json').read_bytes()).hexdigest()}:
        raise ValueError('site source binding differs')
    if packet.get('event_ref') != {'path': 'original-events.json',
           'sha256': hashlib.sha256((attempt / 'original-events.json').read_bytes()).hexdigest()}:
        raise ValueError('event source binding differs')
    summary = process_saved(packet, attempt)
    config = json.loads((attempt / 'config.json').read_text())
    if summary['case_id'] != config['selected_case_id']:
        raise ValueError('saved exact case differs from selected bundle')
    frames = [json.loads(line) for line in verified(attempt, 'video_frames.jsonl').read_text().splitlines() if line.strip()]
    if len(frames) != summary['duration_frames'] or any(
            row.get('carla_frame') != event['frame'] or row.get('video_frame') != i
            for i, (row, event) in enumerate(zip(frames, summary['records']))):
        raise ValueError('original event/video frame join differs')
    diagnostic = attempt / 'fixture-provenance.json'
    if diagnostic.is_file():
        proof = json.loads(diagnostic.read_text())
        if proof.get('diagnostic_fixture') is not True or proof.get('physical_acceptance_claimed') is not False:
            raise ValueError('untrusted diagnostic provenance')
    elif summary['duration_frames'] != 900:
        raise ValueError('production original green capture requires 900 frames')
    return summary


def build_report(attempt):
    summary = measure_green(attempt)
    acquisition = json.loads((attempt / 'acquisition.json').read_text())
    hashes = {name: acquisition[name]['sha256'] for name in REQUIRED}
    return {'format': 'worker-analysis-report',
            'measurements': {'green_exhibition_measurement': {
                'value': {'first_green_frame': summary['exhibition']['frame'],
                          'other_users_at_exhibition': summary['exhibition']['other_users'],
                          'green_frames': summary['green_frames'],
                          'ego_entered_intersection': any(r['ego_in_intersection'] for r in summary['records']),
                          'lawful_presence_verdict': None, 'right_of_way_verdict': None},
                'method': 'measure_green', 'sources': hashes}},
            'analysis_complete': True, 'legal_verdict_claimed': False,
            'limitations': ['Original lawful presence and right-of-way require independent review.']}


def saved_result(attempt, report):
    from worker_exchange.native_output import physical_result, validate_result
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    planned = construction['recording_description']
    summary = measure_green(attempt)
    event_rows = json.loads((attempt / 'original-events.json').read_text())
    site = json.loads((attempt / 'site.json').read_text())
    frame_rows = [json.loads(s) for s in (attempt / 'video_frames.jsonl').read_text().splitlines() if s.strip()]
    output = attempt / 'channels'
    output.mkdir(exist_ok=True)
    values = {
        'official_signal_history': [r['lit_aspects'] for r in event_rows],
        'ego_body_history': [r['ego_xy'] for r in event_rows],
        'other_user_history': [r['other_users'] for r in event_rows],
        'intersection_geometry': [site['intersection_polygon_xy']] * len(event_rows),
        'adjacent_crosswalk_geometry': [site['adjacent_crosswalk_polygon_xy']] * len(event_rows),
        'camera_frame_map': frame_rows}
    evidence = []
    for channel in planned['channels']:
        name = channel['name']
        path = output / (name + '.jsonl')
        with path.open('x') as stream:
            for row, value in zip(frame_rows, values[name]):
                stream.write(json.dumps({'time_s': row['time_s'], 'value': value}, allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': str(path.relative_to(attempt))})
    context = output / 'context.json'
    context.write_text(json.dumps({'official_signal_and_device_context': {'site_ref': summary['site_ref'], 'official_head_id': summary['official_head_id'], 'other_device_review': 'unresolved'},
                                   'participant_lawful_presence_context': {'exhibition': summary['exhibition'], 'lawful_presence_verdict': None, 'right_of_way_verdict': None}}) + '\n')
    for item in planned['context_inputs']:
        evidence.append({'name': item['name'], 'unit': item['unit'],
                         'reference': str(context.relative_to(attempt))})
    result = {'case_id': config['selected_case_id'],
              'measured_values': report['measurements']['green_exhibition_measurement']['value'],
              'target_checks': [{'target': 'original sole circular-green straight intersection observation',
                                 'requested': True, 'measured': True, 'method': 'measure_green',
                                 'tolerance': 0, 'matched': True,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': report['measurements']['green_exhibition_measurement']['sources']}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Saved source assessment pending physical review',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': ['overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                                   'driver_reference.mkv'],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': planned, 'recording_evidence': evidence,
              'realized_observables': {}}
    result = physical_result(attempt, result)
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    attempt = Path(args.attempt).resolve()
    report = build_report(attempt)
    result = saved_result(attempt, report)
    report['physical_checks'] = result['physical_checks']
    report['realized_observables'] = result['realized_observables']
    (attempt / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
