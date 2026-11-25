"""Source-bound pedestrian arrow observations for saved Native output.

This finalizer reports measured frames and preserves the cited permission
question. Diagnostic fixtures exercise the same parsing without legal claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_capture import CAMERAS
from saved_measurement import measure_saved


def _source(root: Path, name: str):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _input(root: Path):
    source, source_sha = _source(root, 'pedestrian-source.json')
    events, events_sha = _source(root, 'original_events.json')
    site, site_sha = _source(root, 'site.json')
    if (source.get('site_ref') != {'path': 'site.json', 'sha256': site_sha} or
            source.get('events_ref') != {'path': 'original_events.json', 'sha256': events_sha}):
        raise ValueError('Pedestrian source does not bind original site and events')
    if not isinstance(events, list) or not events:
        raise ValueError('Original event history missing')
    result = measure_saved(root, source['site_ref'], source['events_ref'],
                           source['case_id'], len(events))
    return source, result, events, {'pedestrian-source.json': source_sha,
                                    'site.json': site_sha,
                                    'original_events.json': events_sha}


def measure_sole_arrow(root: Path):
    _, result, _, hashes = _input(root)
    return {'method': 'measure_sole_arrow', 'sources': hashes,
            'value': {'sole_green_arrow_frames': result['sole_green_arrow_frames'],
                      'original_site_sha256': result['original_site_sha256']}}


def measure_entry_and_device(root: Path):
    _, result, _, hashes = _input(root)
    return {'method': 'measure_entry_and_device', 'sources': hashes,
            'value': {'first_highway_entry': result['first_highway_entry'],
                      'separate_walk_first_frame': result['separate_walk_first_frame'],
                      'separate_walk_frame_count': result['separate_walk_frame_count'],
                      'statutory_permission': 'unresolved'}}


def _native_result(root: Path, source: dict, measurement: dict, rows: list):
    construction, _ = _source(root, 'construction.json')
    description = construction['recording_description']
    channels = root / 'channels'
    channels.mkdir(exist_ok=False)
    values = {
        'sampled_highway_entry': lambda row: {'pedestrian_xy': row['pedestrian_xy'],
                                               'frame': row['frame']},
        'separate_device_timeline': lambda row: {'device_id': row['pedestrian_device_id'],
                                                  'indication': row['pedestrian_device_indication']},
        'official_sole_arrow': lambda row: {'head_id': row['vehicle_head_id'],
                                            'lit_aspects': row['vehicle_head_lit_aspects']},
        'camera_frame_map': lambda row: {'frame': row['frame'],
                                         'original_map': source['frame_map_ref']['path']}}
    evidence = []
    for item in description['channels']:
        name = item['name']
        if name not in values:
            raise ValueError('Selected recording channel lacks original projection: ' + name)
        relative = 'channels/' + name + '.jsonl'
        with (root / relative).open('x') as stream:
            for row in rows:
                stream.write(json.dumps({'time_s': row['sim_time_seconds'],
                                         'value': values[name](row)},
                                        separators=(',', ':'), allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': item['unit'], 'reference': relative})
    for item in description['context_inputs']:
        if item['name'] != 'cited_permission_basis':
            raise ValueError('Unknown selected context: ' + item['name'])
        relative = 'channels/cited_permission_basis.json'
        (root / relative).write_text(json.dumps({'cited_permission_basis': {
            'source': 'NRS 484B.283', 'review_status': 'unresolved'}}) + '\n')
        evidence.append({'name': item['name'], 'unit': item['unit'], 'reference': relative})
    facts = dict(measurement)
    facts.pop('legal_verdict', None)
    return {'case_id': source['case_id'], 'measured_values': facts,
            'target_checks': [{'target': 'original sole arrow, separate device and sampled highway entry',
                               'requested': True, 'measured': True, 'method': 'measure_saved',
                               'tolerance': 0, 'matched': True,
                               'physical_cause_confirmed': False,
                               'cause_evidence': ['pedestrian-source.json', 'original_events.json']}],
            'setup_confirmed': False, 'behavior_attempted': False,
            'maneuver_completed': False,
            'termination_reason': 'Saved source measurement; physical review pending',
            'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
            'video_references': [name + '.mkv' for name in CAMERAS],
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': description, 'recording_evidence': evidence,
            'realized_observables': {}}


def analyze(root: Path, output: Path, report_only=False):
    root, output = Path(root), Path(output)
    source, measured, rows, _ = _input(root)
    report = {'format': 'worker-analysis-report', 'case_id': source['case_id'],
              'measurements': {'sole_arrow_and_facing': measure_sole_arrow(root),
                               'entry_and_separate_device': measure_entry_and_device(root)},
              'limitations': ['Original visibility and statutory NRS 484B.283 permission require review.']}
    if not report_only:
        (root / 'result.json').write_text(json.dumps(_native_result(root, source, measured, rows),
                                                     indent=2, allow_nan=False) + '\n')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
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
