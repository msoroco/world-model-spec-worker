"""Saved-only measurement adapter for the exact C157964 yield cases.

The source seal is checked before any derived output is written. A diagnostic
fixture can exercise this path but cannot establish original physical evidence.
"""

import argparse
import hashlib
import json
from pathlib import Path

from saved_audit import audit_saved
from yield_view import CASES, require


VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
INPUTS = ('original-attempt/seal.json',
          'original-attempt/reviewed-site-packet.json',
          'original-attempt/rows.json',
          'original-attempt/measurement.json')


def required(root, relative):
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()) and path.is_file(),
            'Missing required source: ' + relative)
    return path


def source_hashes(attempt):
    return {name: hashlib.sha256(required(attempt, name).read_bytes()).hexdigest()
            for name in INPUTS}


def measure_yield_source(attempt, case, expected_site_packet_sha256,
                         *, allow_diagnostic=False):
    require(isinstance(expected_site_packet_sha256, str) and
            len(expected_site_packet_sha256) == 64,
            'independent reviewed site hash missing')
    hashes = source_hashes(attempt)
    require(hashes['original-attempt/reviewed-site-packet.json'] ==
            expected_site_packet_sha256,
            'independent reviewed site hash differs')
    audit = audit_saved(attempt / 'original-attempt', case,
                        allow_diagnostic=allow_diagnostic,
                        expected_site_packet_sha256=expected_site_packet_sha256)
    measured = json.loads(required(attempt,
                                   'original-attempt/measurement.json').read_text())
    require(audit['source_integrity'] is True and
            measured['case_id'] == case.case_id,
            'sealed yield measurement differs')
    return measured, hashes, audit


def build(attempt):
    attempt = Path(attempt).resolve()
    config = json.loads(required(attempt, 'config.json').read_text())
    construction = json.loads(required(attempt, 'construction.json').read_text())
    selected = config.get('selected_case_id')
    case = next((c for c in CASES if selected ==
                 config.get('assignment_id', '') + '__' + c.case_id), None)
    require(case is not None and construction.get('case_id') == selected and
            construction.get('law_id') == 'NRS-484B-257-1' and
            construction.get('cell_id') == 'C157964',
            'exact yield construction identity differs')
    diagnostic = config.get('diagnostic_only') is True
    measured, hashes, audit = measure_yield_source(
        attempt, case, config.get('reviewed_site_packet_sha256'),
        allow_diagnostic=diagnostic)
    trace = required(attempt, 'trace.jsonl')
    mapping = required(attempt, 'video_frames.jsonl')
    require(len(trace.read_text().splitlines()) ==
            len(mapping.read_text().splitlines()) == 900,
            'original trace/video frame join differs')
    for view in VIEWS:
        required(attempt, view + '.mkv')
    rows = json.loads(required(attempt, 'original-attempt/rows.json').read_text())
    require(len(rows) == 900, 'original yield row count differs')
    site_packet = json.loads(required(
        attempt, 'original-attempt/reviewed-site-packet.json').read_text())
    site = site_packet['site']
    channel_values = {
        'yield_sign': lambda row: site['yield_sign_present'],
        'nearest_view_reference': lambda row: site['nearest_view_station_m'],
        'ego_speed': lambda row: row['ego_speed_mps'],
        'ego_body_position': lambda row: row['ego_leading_station_m'],
        'through_body_position': lambda row: row['through_center_station_m'],
        'through_phase': lambda row: row['through_phase'],
        'sight_observation': lambda row: row['sight_observation'],
        'governing_control': lambda row: row['control_readback'],
        'across_or_within': lambda row: row['ego_across_or_within'],
    }
    channels = attempt / 'channels'
    require(not channels.exists(), 'derived channel directory already exists')
    channels.mkdir()
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        require(name in channel_values, 'unknown exact yield channel')
        relative = 'channels/' + name + '.jsonl'
        with (attempt / relative).open('x') as stream:
            for row in rows:
                stream.write(json.dumps({'time_s': row['time_s'],
                                         'value': channel_values[name](row)},
                                        sort_keys=True) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': relative})
    context_name = 'reviewed_nearest_view_site_packet'
    context_ref = 'channels/reviewed-site-context.json'
    (attempt / context_ref).write_text(json.dumps({context_name: {
        'site_packet_sha256': hashes['original-attempt/reviewed-site-packet.json'],
        'diagnostic_fixture': diagnostic}}, sort_keys=True) + '\n')
    evidence.append({'name': context_name, 'unit': 'source record',
                     'reference': context_ref})
    report = {'format': 'worker-analysis-report', 'case_id': selected,
              'analysis_complete': True, 'legal_verdict_claimed': False,
              'measurements': {'nearest_view_yield_event': {
                  'value': measured, 'method': 'measure_yield_source',
                  'sources': hashes}},
              'source_audit': audit,
              'limitations': ['Actual sight, immediate hazard, right of way and '
                              'physical completion require independent original review.']}
    result = {'case_id': selected, 'measured_values': measured,
              'target_checks': [{'target': 'source-bound nearest-view yield event',
                                 'requested': config['approach_policy'],
                                 'measured': measured,
                                 'method': 'measure_yield_source',
                                 'tolerance': None, 'matched': False,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': hashes}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'independent original physical review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [view + '.mkv' for view in VIEWS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'provenance_kind': 'synthetic_fixture' if diagnostic else 'native',
              'diagnostic_fixture': diagnostic,
              'physical_acceptance_claimed': False}
    return report, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), 'analysis report already exists')
    report, result = build(args.attempt)
    from worker_exchange.native_output import write_result
    write_result(args.attempt, result)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
