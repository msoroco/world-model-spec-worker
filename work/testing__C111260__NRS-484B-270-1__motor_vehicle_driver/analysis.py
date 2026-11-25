"""Saved-only measurement of the exact original bicycle encounter."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from bicycle_encounter import ASSIGNMENT, CASE_VARIANTS, require, verify_site
from delivery_decode import finalize_delivery
from saved_attempt import VIEWS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, relative):
    path = root / relative
    require(path.is_file() and not path.is_symlink(),
            'Missing required source: ' + relative)
    return path


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n',
                    encoding='utf-8')


def analyze(root):
    """Verify original source joins, then return a measurement and evidence."""
    root = Path(root).resolve()
    config = json.loads(required(root, 'config.json').read_text(encoding='utf-8'))
    case = config.get('selected_case_id')
    require(case in {ASSIGNMENT + '__' + suffix for suffix in CASE_VARIANTS},
            'wrong selected bicycle case')
    variant = CASE_VARIANTS[case.removeprefix(ASSIGNMENT + '__')]
    mode = variant['mode']
    index_path = required(root, 'capture/source-index.json')
    index = json.loads(index_path.read_text(encoding='utf-8'))
    provenance_path = root / 'acquisition-provenance.json'
    provenance = (json.loads(provenance_path.read_text(encoding='utf-8'))
                  if provenance_path.is_file() else {})
    diagnostic = (provenance.get('provenance_kind') == 'synthetic_fixture'
                  and provenance.get('diagnostic_fixture') is True)
    config['_diagnostic_fixture'] = diagnostic
    require(index.get('format') == 'c111260-original-index-v1' and
            index.get('case_id') == case and
            index.get('frame_count') == config['frame_count'],
            'original bicycle source index case or duration mismatch')
    capture = root / 'capture'
    refs = index['sources']
    originals = index.get('camera_originals', {})
    require(isinstance(originals, dict) and set(originals) == set(VIEWS) and
            (diagnostic or all(len(originals[view]) == config['frame_count']
                               for view in VIEWS)),
            'original four-camera PNG inventory missing')
    site_path = required(capture, refs['site']['path'])
    require(sha(site_path) == refs['site']['sha256'],
            'original bicycle site source hash mismatch')
    site = json.loads(site_path.read_text(encoding='utf-8'))
    require(site.get('case_id') == case, 'original bicycle site case differs')
    verify_site(site, capture)
    cameras = {view: refs[view] for view in VIEWS}
    measurement = finalize_delivery(site, capture, refs['events'], cameras,
                                    mode, config['frame_count'])
    require(measurement['rider_kind'] == config['case']['rider_kind'] ==
            variant['rider_kind'],
            'measured rider kind differs from selected case')
    root_map = required(root, 'video_frames.jsonl')
    trace_path = required(root, 'trace.jsonl')
    require(sha(root_map) == refs['frame_map']['sha256'] and
            sha(trace_path) == sha(capture / 'trace.jsonl'),
            'root original frame map or trace differs from sealed capture')
    events = json.loads(required(capture, refs['events']['path']).read_text(encoding='utf-8'))
    trace = [json.loads(line) for line in trace_path.read_text(encoding='utf-8').splitlines()]
    mapping = [json.loads(line) for line in root_map.read_text(encoding='utf-8').splitlines()]
    require(len(events) == len(trace) == len(mapping) == config['frame_count'] and
            all(event['frame'] == motion['frame'] == row['carla_frame'] and
                row['video_frame'] == number and motion['time_s'] == row['time_s']
                for number, (event, motion, row) in
                enumerate(zip(events, trace, mapping))),
            'original bicycle trace/frame/event join differs')
    for view in VIEWS:
        required(root, view + '.mkv')
        require(sha(root / (view + '.mkv')) == refs[view]['sha256'],
                'root original video differs from sealed capture: ' + view)
    measured = {
        'bicycle_encounter_measurement': {
            'method': 'analyze',
            'value': {
                'rider_kind': measurement['rider_kind'],
                'minimum_center_gap_m': measurement['minimum_center_gap_m'],
                'observed_ego_motion_m': measurement['observed_ego_motion_m'],
                'observed_rider_motion_m': measurement['observed_rider_motion_m'],
                'waiting_command_frames': measurement['waiting_command_frames'],
                'travel_command_frames': measurement['travel_command_frames'],
                'lawful_riding_verdict': None,
                'intent_verdict': None,
                'interference_verdict': None},
            'sources': {'capture/source-index.json': sha(index_path),
                        'capture/events.json': refs['events']['sha256'],
                        'capture/site.json': refs['site']['sha256']}}}
    return config, site, events, mapping, measured, measurement


def build_result(root, config, site, events, mapping, measured, measurement):
    """Write converter-facing evidence from the saved originals only."""
    root = Path(root).resolve()
    description = config['case']['recording_description']
    channels = {
        'rider_identity': lambda event: {'ego_id': event['ego_id'],
                                         'rider_id': event['rider_id'],
                                         'rider_kind': site['rider_kind'],
                                         'rider_blueprint_id': event['rider_blueprint_id']},
        'encounter_motion': lambda event: {'ego_xy': event['ego_xy'],
                                           'rider_xy': event['rider_xy'],
                                           'target_speed_mps': event['target_speed_mps'],
                                           'mode_command': event['mode_command']},
        'rider_conduct': lambda event: {'rider_rules_source_path': site['rider_rules_source_path'],
                                       'lawful_riding_verdict': None},
        'camera_frame_map': lambda event: {'frame': event['camera_frame'],
                                           'camera_views': list(VIEWS)},
    }
    evidence = []
    for number, channel in enumerate(description['channels']):
        name = channel['name']
        require(name in channels, 'unimplemented bicycle recording channel: ' + name)
        relative = f'recording-channel-{number}.jsonl'
        with (root / relative).open('x', encoding='utf-8') as stream:
            for event, frame in zip(events, mapping):
                stream.write(json.dumps({'time_s': frame['time_s'],
                                         'value': channels[name](event)}) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': relative})
    for number, item in enumerate(description['context_inputs']):
        require(item['name'] == 'reviewed_original_site',
                'unimplemented bicycle recording context')
        relative = f'recording-context-{number}.json'
        write(root / relative, {'reviewed_original_site': site})
        evidence.append({'name': item['name'], 'unit': item['unit'],
                         'reference': relative})
    result = {
        'case_id': config['selected_case_id'],
        'measured_values': {key: entry['value'] for key, entry in measured.items()},
        'target_checks': [{'target': 'source_sealed_bicycle_observation_count',
                           'requested': config['frame_count'],
                           'measured': len(events),
                           'method': 'original event/frame/video join',
                           'tolerance': 0, 'matched': True,
                           'physical_cause_confirmed': False,
                           'cause_evidence': 'physical encounter requires independent review'}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'saved source processing; physical review pending',
        'physical_failure_flags': ['physical_review_pending'],
        'trace_reference': 'trace.jsonl',
        'video_references': [view + '.mkv' for view in VIEWS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': description,
        'recording_evidence': evidence,
        'realized_observables': {},
        'provenance_kind': ('synthetic_fixture' if config['_diagnostic_fixture']
                            else 'original_saved_source'),
        'diagnostic_fixture': config['_diagnostic_fixture'],
        'legal_verdict_claimed': False,
        'physical_acceptance_claimed': False}
    from worker_exchange.native_output import physical_result, write_result
    result = physical_result(root, result)
    write_result(root, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config, site, events, mapping, measured, measurement = analyze(args.attempt)
    result = build_result(args.attempt, config, site, events, mapping,
                          measured, measurement)
    report = {'format': 'worker-analysis-report',
              'case_id': config['selected_case_id'],
              'analysis_complete': True, 'measurements': measured,
              'physical_checks': result['physical_checks'],
              'realized_observables': result['realized_observables'],
              'diagnostic_fixture': config['_diagnostic_fixture'],
              'legal_verdict_claimed': False,
              'physical_acceptance_claimed': False,
              'limitations': ['Original pixel and actual rider conduct require independent review.',
                              'Lawful riding, intent and interference remain unresolved.']}
    write(args.output, report)


if __name__ == '__main__':
    main()
