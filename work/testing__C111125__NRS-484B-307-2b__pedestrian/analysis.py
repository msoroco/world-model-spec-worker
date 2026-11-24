"""Saved-source pedestrian measurements for diagnostic compatibility.

Synthetic fixture values exercise source joins only. They cannot establish a
Native site, physical crossing, legal permission, or delivery acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_crossing import measure, verify_site
from device_timeline import observe_timeline


def required(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources(root, names):
    return {name: sha(required(root, name)) for name in names}


def measure_signal(facts):
    rows = facts['measurements']
    return {'green_alone_frames': [r['frame'] for r in rows if r['green_alone']],
            'facing_head': True,
            'first_entry_frame': facts['first_highway_entry']['frame'] if facts['first_highway_entry'] else None}


def measure_crosswalk(facts):
    entry = facts['first_highway_entry']
    return {'kind': facts['crosswalk_kind'],
            'entry_inside_crosswalk': entry['in_crosswalk'] if entry else None,
            'highway_entry_frame': entry['frame'] if entry else None}


def measure_device(facts):
    rows = facts['measurements']
    return {'indications_by_frame': [{'frame': r['frame'],
                                       'indication': r['other_device_indication'],
                                       'mode': r['other_device_mode']}
                                      for r in rows],
            'entry_indication': facts['first_highway_entry']['other_device_indication']
                                if facts['first_highway_entry'] else None}


def build_report(root):
    root = Path(root).resolve()
    for name in ('map.json', 'head.json', 'devices.json', 'site.json', 'frames.json'):
        required(root, name)
    site = json.loads((root / 'site.json').read_text())
    verify_site(site, root)
    facts = measure(site, root, {'path': 'frames.json', 'sha256': sha(root / 'frames.json')})
    config = json.loads(required(root, 'config.json').read_text())
    suffix = config['selected_case_id'].split('__')[-1]
    expected = config['case']['scenario_parameters']
    entry = facts['first_highway_entry']
    if facts['crosswalk_kind'] != expected['crosswalk_kind']:
        raise ValueError('Diagnostic crosswalk kind differs from selected case')
    if (entry is not None) != expected['pedestrian_enters_highway']:
        raise ValueError('Diagnostic highway entry differs from selected case')
    if entry and entry['in_crosswalk'] != expected['entry_inside_crosswalk']:
        raise ValueError('Diagnostic crossing boundary differs from selected case')
    if expected.get('device_modes'):
        if [r['other_device_mode'] for r in facts['measurements']] != expected['device_modes']:
            raise ValueError('Diagnostic device timeline differs from selected case')
    elif any(r['other_device_indication'] != expected['other_device_indication']
             for r in facts['measurements']):
        raise ValueError('Diagnostic device state differs from selected case')
    timeline = observe_timeline(facts)
    measurements = {
        'c111125_signal': {'method': 'measure_signal', 'value': measure_signal(facts),
                           'sources': sources(root, ('site.json', 'head.json', 'frames.json'))},
    }
    if suffix not in ('other_device_stop', 'other_device_cross'):
        measurements['c111125_crosswalk'] = {
            'method': 'measure_crosswalk', 'value': measure_crosswalk(facts),
            'sources': sources(root, ('site.json', 'map.json', 'frames.json'))}
    if suffix not in ('marked_cross', 'unmarked_cross', 'outside_cross'):
        measurements['c111125_other_device'] = {
            'method': 'measure_device', 'value': measure_device(facts),
            'sources': sources(root, ('site.json', 'devices.json', 'frames.json'))}
    return {'format': 'worker-analysis-report', 'case_id': config['selected_case_id'],
            'analysis_complete': True, 'measurements': measurements,
            'device_timeline': timeline,
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'legal_verdict_claimed': False, 'physical_acceptance_claimed': False,
            'limitations': ['Diagnostic fixture only; Native site, capture and legal assessment remain unverified.']}


def build_result(root, report):
    """Finalize saved diagnostic observations without asserting physical success."""
    root = Path(root).resolve()
    config = json.loads(required(root, 'config.json').read_text())
    frames = json.loads(required(root, 'frames.json').read_text())
    trace = [json.loads(line) for line in required(root, 'trace.jsonl').read_text().splitlines()]
    mapping = [json.loads(line) for line in required(root, 'video_frames.jsonl').read_text().splitlines()]
    if not frames or len(frames) != len(trace) or len(frames) != len(mapping):
        raise ValueError('Diagnostic frame, trace and video map lengths differ')
    samples = []
    for index, (frame, point, mapped) in enumerate(zip(frames, trace, mapping)):
        if (frame['frame'] != point['frame'] or frame['frame'] != mapped['carla_frame'] or
                mapped['video_frame'] != index or abs(point['time_s'] - mapped['time_s']) > 1e-9 or
                [point['position']['x'], point['position']['y']] != frame['pedestrian_xy']):
            raise ValueError('Diagnostic frame, trace and video map disagree')
        samples.append({'time_s': point['time_s'],
                        'value': {'x': point['position']['x'], 'y': point['position']['y']}})
    channel = root / 'channels/pedestrian_body_center_xy_m.jsonl'
    channel.parent.mkdir(exist_ok=True)
    channel.write_text(''.join(json.dumps(sample, allow_nan=False) + '\n' for sample in samples))
    context = root / 'contexts/source_provenance.json'
    context.parent.mkdir(exist_ok=True)
    source_hashes = sources(root, ('site.json', 'map.json', 'head.json', 'devices.json',
                                   'frames.json', 'trace.jsonl', 'video_frames.jsonl'))
    context.write_text(json.dumps({'source_provenance': {
        'kind': 'synthetic_fixture', 'source_sha256': source_hashes}}, indent=2) + '\n')
    expectation = config['case']['scenario_parameters']['pedestrian_enters_highway']
    observed = report['measurements']['c111125_signal']['value']['first_entry_frame'] is not None
    return {
        'case_id': config['selected_case_id'], 'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
        'measured_values': report['measurements'],
        'target_checks': [{
            'target': 'pedestrian highway entry in diagnostic frames',
            'requested': expectation, 'measured': observed,
            'method': 'saved frame, map, trace and video-map join',
            'tolerance': 0, 'matched': observed == expectation,
            'physical_cause_confirmed': False,
            'cause_evidence': {'synthetic_source_sha256': source_hashes,
                               'physical_source': 'unavailable'}}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'Synthetic diagnostic source join complete; physical run unavailable',
        'physical_failure_flags': {'physical_site_unverified': True},
        'trace_reference': 'trace.jsonl',
        'video_references': ['overview.mkv', 'approach.mkv',
                             'reference_corner.mkv', 'driver_reference.mkv'],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['case']['recording_description'],
        'recording_evidence': [
            {'name': 'pedestrian_body_center_xy_m', 'unit': 'structured',
             'reference': 'channels/pedestrian_body_center_xy_m.jsonl'},
            {'name': 'source_provenance', 'unit': 'metadata',
             'reference': 'contexts/source_provenance.json'}],
        'realized_observables': {}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = build_report(args.attempt)
    Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    root = Path(args.attempt).resolve()
    result_path = root / 'result.json'
    if result_path.exists():
        raise ValueError('Retain prior result; choose a fresh attempt')
    result = build_result(root, report)
    with result_path.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    main()
