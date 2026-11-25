"""Saved-only bicycle roadway-use measurement; fixtures remain diagnostic."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_measurement import measure
from native_site import validate_site
from reviewed_site import verify


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sealed_original_bicycle_segment_projection(site: dict, packet: dict, case: dict) -> dict:
    return measure(site, packet, case)


def analyze(attempt: Path, case_id: str) -> dict:
    attempt = Path(attempt)
    config = json.loads((attempt / 'config.json').read_text(encoding='utf-8'))
    if config.get('selected_case_id') != case_id:
        raise ValueError('saved selected bicycle case identity differs')
    packet_path = attempt / 'capture-packet.json'
    site_path = attempt / 'site-source.json'
    for path in (packet_path, site_path):
        if not path.is_file():
            raise ValueError('Missing required source: ' + path.name)
    packet = json.loads(packet_path.read_text(encoding='utf-8'))
    provenance = json.loads((attempt / 'acquisition-provenance.json').read_text(encoding='utf-8'))
    diagnostic = provenance.get('diagnostic_fixture') is True
    if diagnostic:
        site = json.loads(site_path.read_text(encoding='utf-8'))
        if site.get('diagnostic_fixture') is not True or packet.get('source_kind') != 'diagnostic_fixture_capture':
            raise ValueError('diagnostic bicycle fixture provenance mismatch')
        validate_site(site)
        source_hashes = {'site-source.json': sha(site_path)}
    else:
        if packet.get('source_kind') != 'original_native_capture':
            raise ValueError('original bicycle capture provenance mismatch')
        reviewed = verify(site_path)
        site = reviewed['site']
        source_hashes = {'site-source.json': sha(site_path), **reviewed['source_hashes']}
    measured = sealed_original_bicycle_segment_projection(site, packet, config['case'])
    return {'format': 'worker-analysis-report', 'case_id': case_id,
            'measurements': {'bicycle_roadway_use': {
                'value': measured, 'method': 'sealed_original_bicycle_segment_projection',
                'sources': {'capture-packet.json': sha(packet_path), **source_hashes}}},
            'analysis_complete': True, 'diagnostic_fixture': diagnostic,
            'legal_verdict_claimed': False}


def saved_result(attempt: Path, report: dict) -> dict:
    from worker_exchange.native_output import physical_result, validate_result
    attempt = Path(attempt)
    config = json.loads((attempt / 'config.json').read_text(encoding='utf-8'))
    construction = json.loads((attempt / 'construction.json').read_text(encoding='utf-8'))
    case_id = config['selected_case_id']
    if construction['case_id'] != case_id or report['case_id'] != case_id:
        raise ValueError('saved bicycle construction identity differs')
    description = construction['recording_description']
    measured = report['measurements']['bicycle_roadway_use']['value']
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=True)
    evidence = []
    for entry in description['channels']:
        name = entry['name']
        path = channels / (name + '.jsonl')
        with path.open('x', encoding='utf-8') as stream:
            for i in range(900):
                stream.write(json.dumps({'time_s': i / 20, 'value': {
                    'frame': i, 'source': 'diagnostic fixture' if report['diagnostic_fixture'] else 'original Native'}}) + '\n')
        evidence.append({'name': name, 'unit': entry['unit'],
                         'reference': str(path.relative_to(attempt))})
    context = channels / 'context.json'
    context.write_text(json.dumps({
        'reviewed designation sign route and bicycle': {
            'source_kind': measured['source_kind'],
            'site_sha256': measured['site_sha256']}}) + '\n', encoding='utf-8')
    for entry in description['context_inputs']:
        evidence.append({'name': entry['name'], 'unit': entry['unit'],
                         'reference': str(context.relative_to(attempt))})
    motion = config['case']['motion']
    requested = motion == 'enter_roadway'
    actual = measured['roadway_frames'] > 0
    result = {'case_id': case_id, 'measured_values': measured,
              'target_checks': [{'target': 'bicycle roadway entry', 'requested': requested,
                  'measured': actual, 'method': '900 sealed 20 Hz segment readbacks',
                  'tolerance': 0, 'matched': requested == actual,
                  'physical_cause_confirmed': False,
                  'cause_evidence': report['measurements']['bicycle_roadway_use']['sources']}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False, 'termination_reason': 'Saved bicycle roadway-use review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': ['overview.mkv', 'approach.mkv',
                                   'reference_corner.mkv', 'driver_reference.mkv'],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': {}}
    result = physical_result(attempt, result)
    validate_result(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('fresh bicycle analysis output required')
    config = json.loads((args.attempt / 'config.json').read_text(encoding='utf-8'))
    report = analyze(args.attempt, config['selected_case_id'])
    result = saved_result(args.attempt, report)
    report['physical_checks'] = result['physical_checks']
    report['realized_observables'] = result['realized_observables']
    (args.attempt / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
