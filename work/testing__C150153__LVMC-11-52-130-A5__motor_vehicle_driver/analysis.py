"""Selected saved-source elevator measurement; no legal or pixel verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_finalizer import finalize
from physical_outcomes import evaluate
from parking import CASES

SOURCES = ('reviewed-site/packet.json', 'history.jsonl', 'comparison-context.json')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def required(root: Path, relative: str) -> Path:
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Missing required source: ' + relative)
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(root: Path, relative: str) -> list[dict]:
    return [json.loads(line) for line in required(root, relative).read_text().splitlines() if line]


def measure_elevator_requirement(root: Path, saved: dict, case, site: dict) -> dict:
    """Report recorded frontage, side gap, activity and necessity source identity."""
    original = rows(root, 'history.jsonl')
    context = json.loads(required(root, 'comparison-context.json').read_text())
    if context['case_id'] != saved['case_id'] or context['history_sha256'] != sha(required(root, 'history.jsonl')):
        raise ValueError('Original comparison context differs')
    if len(original) != 900:
        raise ValueError('Original elevator history needs 900 joined samples')
    physical = evaluate(case, original, site, sha(required(root, 'history.jsonl')),
                        sha(required(root, 'reviewed-site/packet.json')),
                        diagnostic_fixture=bool(json.loads(required(root, 'acquisition-provenance.json').read_text()).get('diagnostic_fixture')) if (root / 'acquisition-provenance.json').is_file() else False)
    return {'observed_regions': saved['observed_regions'],
            'observed_activities': saved['observed_activities'],
            'minimum_side_gap_m': saved['min_side_gap_m'],
            'front_overlap_frames': saved['front_overlap_frames'],
            'five_feet_reference_m': saved['five_feet_m_reference'],
            'exception_source_sha256': context.get('exception_source_sha256'),
            'physical_maneuver_status': physical['physical_checks']['maneuver']['status'],
            'legal_applicability': 'unresolved_from_original_source_review'}


def channel_evidence(root: Path, description: dict, history: list[dict]) -> list[dict]:
    if len(history) != 900:
        raise ValueError('Original channels need 900 samples')
    packet = json.loads(required(root, 'reviewed-site/packet.json').read_text())
    fixture = packet['site']['fixture']
    channels = root / 'channels'
    channels.mkdir(exist_ok=True)
    selectors = {
        'vehicle_body_footprint': lambda row: {key: row[key] for key in ('body_west_x_m', 'body_east_x_m', 'body_curb_gap_m', 'ego_position_m')},
        'fixture_frontage_and_side_extents': lambda row: {
            'reviewed_west_x_m': fixture['west_x_m'],
            'reviewed_east_x_m': fixture['east_x_m'],
            'fixture_physically_present': row['fixture_physically_present'],
            'fixture_geometry_sha256': row['fixture_geometry_sha256']},
        'activity': lambda row: {key: row[key] for key in ('activity_observation', 'ego_speed_mps')},
        'exception_circumstances': lambda row: {key: row[key] for key in ('exception_kind', 'exception_source_sha256') if key in row},
        'jurisdiction_and_sidewalk': lambda row: {key: row[key] for key in ('municipal_jurisdiction_sha256', 'sidewalk_sha256') if key in row},
    }
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in selectors:
            raise ValueError('Unknown elevator observation channel: ' + name)
        relative = 'channels/' + name + '.jsonl'
        lines = [{'frame': row['original_frame'], 'time_s': row['time_s'],
                  'value': selectors[name](row)} for row in history]
        (root / relative).write_text(''.join(json.dumps(line, allow_nan=False) + '\n' for line in lines))
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': relative})
    values = {'reviewed_sidewalk_elevator_site': {'site_packet_sha256': sha(required(root, 'reviewed-site/packet.json')),
                                                  'fixture_identity_sha256': packet['site']['fixture_identity_sha256'],
                                                  'fixture_geometry_sha256': packet['site']['fixture_geometry_sha256'],
                                                  'fixture': fixture},
              'reviewed_vehicle_dimensions': {'ego_blueprint_sha256': packet['site']['ego_blueprint_sha256']}}
    for channel in description['context_inputs']:
        name = channel['name']
        relative = 'channels/' + name + '.json'
        (root / relative).write_text(json.dumps({name: values[name]}, allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': relative})
    return evidence


def run(root: Path, output: Path) -> dict:
    root = Path(root).resolve()
    for name in SOURCES:
        required(root, name)
    config = json.loads(required(root, 'config.json').read_text())
    packet = json.loads(required(root, SOURCES[0]).read_text())
    case_id = config['selected_case_id']
    local = case_id.removeprefix(packet['assignment_id'] + '__')
    case = next((item for item in CASES if item.id == local), None)
    if case is None or case_id != packet['assignment_id'] + '__' + local:
        raise ValueError('Selected exact elevator case differs')
    provenance = json.loads((root / 'acquisition-provenance.json').read_text()) if (root / 'acquisition-provenance.json').is_file() else {}
    diagnostic = provenance.get('diagnostic_fixture') is True
    saved = finalize(root, root / SOURCES[0], root / 'reviewed-site/sources',
                     diagnostic_fixture=diagnostic,
                     decoder=(lambda path, name: 900) if diagnostic else None)
    value = measure_elevator_requirement(root, saved, case, packet['site'])
    physical = evaluate(case, rows(root, 'history.jsonl'), packet['site'],
                        sha(required(root, 'history.jsonl')),
                        sha(required(root, SOURCES[0])), diagnostic_fixture=diagnostic)
    hashes = {name: sha(required(root, name)) for name in SOURCES}
    measurement = {'method': 'measure_elevator_requirement', 'value': value, 'sources': hashes}
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'measurements': {'observed_elevator_requirement': measurement},
              'legal_applicability': 'unresolved', 'analysis_complete': True,
              'limitations': ['Original pixel review and statutory boundary interpretation remain separate']}
    history = rows(root, 'history.jsonl')
    description = config['recording_description']
    evidence = channel_evidence(root, description, history)
    from worker_exchange.native_output import physical_result, validate_result
    target = {'target': 'case_specific_elevator_body_region', 'requested': local,
              'measured': value['observed_regions'], 'method': 'original saved body interval and reviewed site geometry',
              'tolerance': 0, 'matched': value['physical_maneuver_status'] == 'met',
              'physical_cause_confirmed': False, 'cause_evidence': 'Original pixel and legal review unresolved'}
    result = physical_result(root, {'case_id': case_id,
                'measured_values': {'observed_elevator_requirement': value},
                'target_checks': [target], 'setup_confirmed': False,
                'behavior_attempted': False, 'maneuver_completed': False,
                'termination_reason': 'Saved original source measured; legal review unresolved',
                'physical_failure_flags': {}, 'trace_reference': 'trace.jsonl',
                'video_references': ['raw.mkv'], 'video_frame_map_reference': 'video_frames.jsonl',
                'recording_description': description, 'recording_evidence': evidence,
                'realized_observables': {}})
    result['physical_checks']['maneuver'] = physical['physical_checks']['maneuver']
    result['maneuver_completed'] = physical['maneuver_completed']
    result['physical_observations']['elevator'] = physical['realized_observables'] or {}
    validate_result(result)
    (root / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.attempt, args.output)


if __name__ == '__main__':
    main()
