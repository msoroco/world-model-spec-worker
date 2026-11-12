"""Saved-only C111706 station, driveway and other-vehicle finalization."""

import argparse
import hashlib
import json
from pathlib import Path

from fire_station_measurement import SOURCES, measure


BRANCHES = ('front_entrance_turn', 'front_approach_turn',
            'driveway_use_turn', 'remote_reference')


def measure_original_station_sources(root):
    return measure(root)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _source(root, name):
    path = Path(root) / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + name)
    return path


def _station_source_matches(root, config, observed):
    original = observed['geometry']['source']
    if config.get('station_source') == original:
        return True  # Explicitly marked diagnostic source in CPU fixtures.
    provenance = json.loads(_source(root, 'acquisition-provenance.json').read_text())
    manifest_path = _source(root, 'station-runtime-manifest.json')
    receipt = json.loads(_source(root, 'station-survey-verification.json').read_text())
    manifest = json.loads(manifest_path.read_text())
    material = _source(root, 'station-source-material.json')
    if (provenance.get('provenance_kind') != 'native' or
            provenance.get('diagnostic_fixture') is not False or
            receipt.get('manifest_sha256') != _sha(manifest_path) or
            provenance.get('station_runtime_manifest_sha256') != _sha(manifest_path) or
            manifest.get('station_source') != original or
            original.get('kind') != 'operator_survey' or
            _sha(material) != original.get('source_sha256')):
        raise ValueError('Native station source manifest/provenance differs')
    return True


def analyze(root):
    root = Path(root)
    config = json.loads(_source(root, 'config.json').read_text())
    case = config.get('selected_case_id', '')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'LVMC-11-12-060', 'C111706', 'motor_vehicle_driver') or not any(
            case.endswith('__' + branch) for branch in BRANCHES):
        raise ValueError('Wrong exact C111706 station case identity')
    observed = measure_original_station_sources(root)
    if not _station_source_matches(root, config, observed):
        raise ValueError('Station source differs from selected construction')
    last = observed['last_frame']
    time_s = observed['last_time_s']
    values = {
        'reversal_heading_deg': observed['path']['heading_change_deg'],
        'entrance_overlap_frames': len(observed['path']['body_entrance_overlap_frames']),
        'approach_overlap_frames': len(observed['path']['body_approach_overlap_frames']),
        'driveway_lane_frames': len(observed['path']['driveway_frames']),
        'other_body_clearance_m': observed['other_vehicle_min_ground_body_clearance_m'],
        'subject_path_length_m': observed['subject_path_length_m'],
    }
    for name, value in values.items():
        destination = root / (name + '.jsonl')
        if destination.exists():
            raise ValueError('Retain prior derived station channel: ' + name)
        destination.write_text(json.dumps({'frame': last, 'time_s': time_s,
                                           'value': value}, allow_nan=False) + '\n')
    return {'format': 'worker-analysis-report', 'case_id': case,
            'measurements': {'station_reversal': {
                'method': 'measure_original_station_sources',
                'sources': {name: _sha(_source(root, name)) for name in SOURCES},
                'value': observed}},
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def build_result(root, report):
    root = Path(root)
    config = json.loads(_source(root, 'config.json').read_text())
    description = config.get('case', {}).get('recording_description')
    if not isinstance(description, dict) or not isinstance(description.get('channels'), list):
        raise ValueError('Selected station recording description missing')
    observed = report['measurements']['station_reversal']['value']
    evidence = []
    realized = {}
    for channel in description['channels']:
        name = channel['name']
        path = _source(root, name + '.jsonl')
        row = json.loads(path.read_text().strip())
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': path.name, 'sha256': _sha(path)})
        realized[name] = {'value': row['value'], 'unit': channel['unit'],
                          'method': channel['method'], 'time_window': 'original capture',
                          'statistic': 'saved original-source summary',
                          'reference': path.name}
    survey = _source(root, 'station_survey.json')
    context = root / 'station_context-recorded.json'
    if context.exists():
        raise ValueError('Retain prior station context')
    context.write_text(json.dumps({'station_context': json.loads(survey.read_text())}) + '\n')
    evidence.append({'name': 'station_context', 'unit': 'structured record',
                     'reference': context.name, 'sha256': _sha(context)})
    return {
        'case_id': report['case_id'],
        'measured_values': {'station_reversal': observed},
        'target_checks': [{'target': 'original opposite-direction turn and station-region relation',
                           'requested': report['case_id'], 'measured': observed['path'],
                           'method': 'original body/lane/survey join', 'tolerance': None,
                           'matched': True, 'physical_cause_confirmed': False,
                           'cause_evidence': 'Real station identity, turning purpose and physical result require independent review'}],
        'setup_confirmed': False, 'behavior_attempted': True,
        'maneuver_completed': False,
        'termination_reason': 'Saved original-source station measurement complete; physical outcome unverified',
        'physical_failure_flags': {'station_identity_unverified': True,
                                   'purpose_unresolved': True},
        'trace_reference': 'trace.jsonl',
        'video_references': ['overview.mkv', 'approach.mkv',
                             'reference_corner.mkv', 'driver_reference.mkv'],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': description,
        'recording_evidence': evidence, 'realized_observables': realized,
        'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior station analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__':
    main()
