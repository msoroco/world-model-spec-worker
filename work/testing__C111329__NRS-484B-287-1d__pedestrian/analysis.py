"""Saved-only, source-bound pedestrian crossing analysis.

This measures the recorded route and device state. It does not decide whether
NRS 484B.290 applies or whether the recorded device has legal authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_acquisition import CAMERAS
from saved_measurement import measure_acquisition


def source(root: Path, ref: dict):
    name = ref.get('path')
    if not isinstance(name, str) or Path(name).is_absolute() or '..' in Path(name).parts:
        raise ValueError('invalid original source reference')
    path = (root / name).resolve(strict=True)
    if not path.is_relative_to(root.resolve()) or path.is_symlink():
        raise ValueError('original source escaped attempt')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref.get('sha256'):
        raise ValueError('original source digest changed: ' + name)
    return json.loads(raw), raw


def measure_crossing_route(measured: dict, expected: dict):
    return {'planned_route_kind': expected['route_kind'],
            'observed_start_xy': measured['observed_start_xy'],
            'observed_end_xy': measured['observed_end_xy'],
            'observed_inside_frames': measured['observed_inside_frames']}


def measure_device_authority(measured: dict, expected: dict):
    return {'planned_diagonal_authorization': expected['source_backed_diagonal_authorization'],
            'authorization_observed_during_inside': measured['authorization_observed_during_inside'],
            'device_source_hashes': measured['device_source_hashes'],
            'legal_authority_review': 'unresolved'}


def measure_exception_context():
    return {'NRS_484B_290_exception': 'unresolved'}


def analyze(attempt: Path, output: Path, report_only: bool = False):
    root = Path(attempt).resolve(strict=True)
    if not (root / 'pedestrian-source.json').is_file():
        raise ValueError('Missing required source: pedestrian-source.json')
    declaration = json.loads((root / 'pedestrian-source.json').read_text())
    if declaration.get('format') != 'c111329-original-source-v1':
        raise ValueError('C111329 original source declaration missing')
    site, _ = source(root, declaration['site_ref'])
    packet, _ = source(root, declaration['native_acquisition_ref'])
    camera, _ = source(root, declaration['camera_manifest_ref'])
    config = json.loads((root / 'config.json').read_text())
    expected = config['scenario_parameters']
    diagnostic = declaration.get('diagnostic_fixture') is True
    if diagnostic != (packet.get('diagnostic') is True) or camera.get('native_rows_sha256') != packet.get('rows_sha256'):
        raise ValueError('source diagnostic provenance differs')
    if packet['case_id'] != config['selected_case_id'] or declaration['case_id'] != packet['case_id']:
        raise ValueError('source exact case differs')
    frames = packet['frame_count']
    if frames != config['frame_count'] and not diagnostic:
        raise ValueError('full original frame count missing')
    measured = measure_acquisition(site, packet, case_id=packet['case_id'],
                                   route_kind=expected['route_kind'],
                                   authorization=expected['source_backed_diagonal_authorization'],
                                   expected_frames=frames, allow_diagnostic=diagnostic)
    report = {'format': 'worker-analysis-report', 'case_id': packet['case_id'],
              'measurements': {
                  'crossing_route': {'method': 'measure_crossing_route',
                                     'sources': {'pedestrian-source.json': hashlib.sha256((root / 'pedestrian-source.json').read_bytes()).hexdigest(),
                                                 declaration['site_ref']['path']: declaration['site_ref']['sha256'],
                                                 declaration['native_acquisition_ref']['path']: declaration['native_acquisition_ref']['sha256']},
                                     'value': measure_crossing_route(measured, expected)},
                  'official_device_authority': {'method': 'measure_device_authority',
                                                'sources': {declaration['site_ref']['path']: declaration['site_ref']['sha256'],
                                                            declaration['native_acquisition_ref']['path']: declaration['native_acquisition_ref']['sha256']},
                                                'value': measure_device_authority(measured, expected)},
                  'exception_context': {'method': 'measure_exception_context',
                                        'sources': {'pedestrian-source.json': hashlib.sha256((root / 'pedestrian-source.json').read_bytes()).hexdigest()},
                                        'value': measure_exception_context()}},
              'limitations': ['Original device authority and NRS 484B.290 exception require independent review.',
                              'Diagnostic fixtures cannot establish physical crossing.']}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    if report_only:
        return report
    from worker_exchange.native_output import write_result
    channels = root / 'channels'
    channels.mkdir(exist_ok=False)
    projections = {
        'walker_center_xy': lambda row: row['walker_center_xy'],
        'device_readback': lambda row: row['devices'],
        'camera_frame_map': lambda row: row['camera_frames'],
    }
    evidence = []
    for channel in config['case']['recording_description']['channels']:
        name = channel['name']
        path = channels / (name + '.jsonl')
        with path.open('x', encoding='utf-8') as stream:
            for row in packet['rows']:
                stream.write(json.dumps({'time_s': row['elapsed_seconds'],
                                         'value': projections[name](row)},
                                        separators=(',', ':'), allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': 'channels/' + path.name})
    for context in config['case']['recording_description']['context_inputs']:
        name = context['name']
        path = channels / (name + '.json')
        path.write_text(json.dumps({name: {'source_status': 'unresolved' if name == 'NRS_484B_290_exception' else 'source_hash_bound'}},
                                   sort_keys=True) + '\n')
        evidence.append({'name': name, 'unit': context['unit'], 'reference': 'channels/' + path.name})
    result = {'case_id': packet['case_id'], 'measured_values': measured,
              'target_checks': [{'target': 'original crossing route and device readback',
                                 'requested': True, 'measured': True, 'method': 'measure_acquisition',
                                 'tolerance': 0, 'matched': True, 'physical_cause_confirmed': False,
                                 'cause_evidence': ['pedestrian-source.json', 'native-acquisition.json']}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Saved source measurement; physical and legal review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['case']['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {}}
    write_result(root, result)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report-only', action='store_true')
    args = parser.parse_args()
    analyze(args.attempt, args.output, args.report_only)


if __name__ == '__main__':
    main()
