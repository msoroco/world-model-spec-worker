"""Saved-only exact pedestrian analysis on sealed original crossing sources."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from analysis import build_report as diagnostic_report, build_result as diagnostic_result
from delivery_audit import audit as audit_original
from native_capture import ASSIGNMENT, CAMERAS
from native_crossing import measure, source


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def analyze_original(root, case_id):
    from worker_exchange.native_output import physical_result, validate_result

    root = Path(root).resolve()
    suffix = case_id.removeprefix(ASSIGNMENT + '__')
    if case_id != ASSIGNMENT + '__' + suffix:
        raise ValueError('wrong exact pedestrian case')
    receipt = json.loads((root / 'capture-receipt.json').read_text())
    site_ref = receipt.get('reviewed_site_source')
    if not isinstance(site_ref, dict):
        raise ValueError('Missing required source: reviewed site')
    site = json.loads(source(site_ref, root).read_text())
    protocol = audit_original(root, site_ref, suffix, require_reviewed=True)
    facts = measure(site, root, receipt['original_frames'])
    rows = facts['measurements']
    mapping = [json.loads(line) for line in (root / 'video_frames.jsonl').read_text().splitlines()]
    trace = [json.loads(line) for line in (root / 'trace.jsonl').read_text().splitlines()]
    if len(rows) != len(mapping) or len(rows) != len(trace) or len(rows) != 900:
        raise ValueError('Missing required source: complete original timestamp join')
    for index, (fact, mapped, point) in enumerate(zip(rows, mapping, trace)):
        if (mapped.get('video_frame') != index or mapped.get('carla_frame') != fact['frame'] or
                point.get('frame') != fact['frame'] or
                abs(mapped.get('time_s', -1) - point.get('time_s', -2)) > .001):
            raise ValueError('original pedestrian timestamp/frame join differs')
    channel_root = root / 'channels'
    channel_root.mkdir(exist_ok=False)
    original_rows = json.loads((root / 'original-frames.json').read_text())
    channel = channel_root / 'pedestrian_body_center_xy_m.jsonl'
    channel.write_text(''.join(json.dumps({
        'time_s': row['elapsed_seconds'],
        'value': {'x': row['pedestrian_xy'][0], 'y': row['pedestrian_xy'][1]}},
        allow_nan=False) + '\n' for row in original_rows))
    context = channel_root / 'source_provenance.json'
    context.write_text(json.dumps({'source_provenance': {
        'kind': 'audited_saved_original',
        'site_sha256': site_ref['sha256'],
        'original_frames_sha256': receipt['original_frames']['sha256'],
        'capture_receipt_sha256': _sha(root / 'capture-receipt.json')}},
        sort_keys=True) + '\n')
    config = json.loads((root / 'config.json').read_text())
    recording = json.loads((root / 'construction.json').read_text())['recording_description']
    measurements = {
        'c111125_signal': {'method': 'measure_signal',
                           'value': {'green_alone_frames': [r['frame'] for r in rows if r['green_alone']],
                                     'facing_head': True,
                                     'first_entry_frame': facts['first_highway_entry']['frame'] if facts['first_highway_entry'] else None},
                           'sources': {'site-source.json': site_ref['sha256'],
                                       'original-frames.json': receipt['original_frames']['sha256']}},
        'c111125_crosswalk': {'method': 'measure_crosswalk',
                              'value': {'kind': facts['crosswalk_kind'],
                                        'entry_inside_crosswalk': facts['first_highway_entry']['in_crosswalk'] if facts['first_highway_entry'] else None},
                              'sources': {'site-source.json': site_ref['sha256'],
                                          'original-frames.json': receipt['original_frames']['sha256']}},
        'c111125_other_device': {'method': 'measure_device',
                                 'value': protocol['device_timeline'],
                                 'sources': {'site-source.json': site_ref['sha256'],
                                             'original-frames.json': receipt['original_frames']['sha256']}},
    }
    result = {
        'case_id': case_id, 'measured_values': measurements,
        'target_checks': [{'target': 'pedestrian source-bound crossing observation',
                           'requested': True,
                           'measured': protocol['source_join_passed'],
                           'method': 'saved original pedestrian/device/pixel and trace join',
                           'tolerance': 0, 'matched': protocol['source_join_passed'],
                           'physical_cause_confirmed': False,
                           'cause_evidence': {'site': site_ref['sha256'],
                                              'frames': receipt['original_frames']['sha256']}}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'Saved original crossing measured; legal review unresolved',
        'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': recording,
        'recording_evidence': [
            {'name': 'pedestrian_body_center_xy_m', 'unit': 'structured',
             'reference': str(channel.relative_to(root))},
            {'name': 'source_provenance', 'unit': 'metadata',
             'reference': str(context.relative_to(root))}],
        'realized_observables': {},
    }
    result = physical_result(root, result)
    validate_result(result)
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'analysis_complete': True, 'measurements': measurements,
              'device_timeline': protocol['device_timeline'],
              'physical_checks': result['physical_checks'],
              'realized_observables': result['realized_observables'],
              'provenance_kind': result['provenance_kind'],
              'diagnostic_fixture': result['diagnostic_fixture'],
              'legal_verdict_claimed': False,
              'physical_acceptance_claimed': False,
              'limitations': ['Original device applicability and legal permission require human source review.']}
    return report, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    root = Path(args.attempt).resolve()
    config = json.loads((root / 'config.json').read_text())
    case_id = config['selected_case_id']
    if (root / 'original-frames.json').is_file():
        report, result = analyze_original(root, case_id)
    else:
        report = diagnostic_report(root)
        result = diagnostic_result(root, report)
    output = Path(args.output)
    if output.exists() or (root / 'result.json').exists():
        raise ValueError('Retain prior saved analysis result')
    _write(root / 'result.json', result)
    _write(output, report)


if __name__ == '__main__':
    main()
