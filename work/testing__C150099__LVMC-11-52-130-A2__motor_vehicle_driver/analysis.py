"""Saved-only fire-lane measurement from immutable original frame sources."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_audit import audit_planned_case
from source_packet import validate_packet


def required(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.is_file():
        raise ValueError('Missing required source: ' + relative)
    return path


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_fire_lane(attempt: Path, config: dict) -> tuple[dict, list[dict]]:
    """One selected law measurement, with no official or legal conclusion."""
    names = ('original-attempt/history.jsonl', 'original-attempt/inventory.json',
             'original-attempt/frame_map.json', 'original-attempt/site.json')
    paths = {name: required(attempt, name) for name in names}
    inventory = json.loads(paths['original-attempt/inventory.json'].read_text())
    if inventory.get('case_id') != config['selected_case_id']:
        raise ValueError('original inventory case changed')
    if digest(paths['original-attempt/history.jsonl']) != inventory.get('history_sha256'):
        raise ValueError('sealed original history changed')
    if digest(paths['original-attempt/frame_map.json']) != inventory.get('frame_map_sha256'):
        raise ValueError('sealed original frame map changed')
    if inventory.get('diagnostic_fixture') is False:
        packet_path = required(attempt, 'original-attempt/reviewed-packet.json')
        if digest(packet_path) != inventory.get('site_sha256'):
            raise ValueError('reviewed original packet changed')
        reviewed_site = validate_packet(packet_path, config['selected_case_id'])
        if reviewed_site != json.loads(paths['original-attempt/site.json'].read_text()):
            raise ValueError('reviewed original site differs from captured site')
    original = rows(paths['original-attempt/history.jsonl'])
    if not original:
        raise ValueError('original fire-lane history empty')
    if inventory.get('diagnostic_fixture') is True:
        if not 2 <= len(original) <= 20:
            raise ValueError('diagnostic fire-lane history length invalid')
    elif len(original) != config['frame_count']:
        raise ValueError('original fire-lane history duration differs')
    audited = audit_planned_case(paths['original-attempt/history.jsonl'],
                                 inventory['history_sha256'],
                                 config['selected_case_id'],
                                 inventory['site_sha256'], frames=len(original))
    mapping = json.loads(paths['original-attempt/frame_map.json'].read_text())['frames']
    trace = rows(required(attempt, 'trace.jsonl'))
    video_map = rows(required(attempt, 'video_frames.jsonl'))
    if not (len(original) == len(mapping) == len(trace) == len(video_map)):
        raise ValueError('original frame/trace/video count differs')
    for index, (source, frame, motion, video) in enumerate(zip(original, mapping, trace, video_map)):
        if (source['original_frame'] != frame['frame'] or
                source['time_s'] != frame['time_s'] or
                motion.get('frame') != frame['frame'] or
                motion.get('time_s') != frame['time_s'] or
                video.get('video_frame') != index or
                video.get('carla_frame') != frame['frame'] or
                video.get('time_s') != frame['time_s']):
            raise ValueError('original frame/trace/video identity differs')
    site = json.loads(paths['original-attempt/site.json'].read_text())
    for key in ('map_sha256', 'jurisdiction_sha256',
                'fire_code_designation_sha256', 'posting_authority_sha256',
                'posted_extent_sha256', 'sign_identity_sha256',
                'sign_appearance_sha256', 'curb_geometry_sha256',
                'property_source_sha256', 'route_sha256', 'weather_sha256'):
        if site.get(key) != audited['fixed_sources'].get(key):
            raise ValueError('original reviewed site differs: ' + key)
    observed = audited['observed']
    value = {
        'hold_frame_count': observed['hold_frame_count'],
        'hold_overlap_frames': observed['hold_overlap_frames'],
        'activity': observed['activity'],
        'attended': observed['attended'],
        'property_kind': observed['property_kind'],
        'target_region': observed['target_region'],
        'exception': observed['exception'],
        'official_designation_judgment': None,
        'statutory_exception_judgment': None,
    }
    measurement = {'value': value, 'method': 'measure_fire_lane',
                   'sources': {name: digest(path) for name, path in paths.items()}}
    return measurement, original


def build(attempt: Path) -> tuple[dict, dict]:
    attempt = Path(attempt).resolve()
    config = json.loads(required(attempt, 'config.json').read_text())
    construction = json.loads(required(attempt, 'construction.json').read_text())
    if construction['case_id'] != config['selected_case_id']:
        raise ValueError('selected fire-lane construction differs')
    measurement, original = measure_fire_lane(attempt, config)
    report = {
        'format': 'worker-analysis-report', 'case_id': config['selected_case_id'],
        'measurements': {'fire_lane_occupation': measurement},
        'analysis_complete': True, 'legal_verdict_claimed': False,
        'limitations': ['Diagnostic fixtures do not establish City designation or physical visibility.',
                        'Original sign pixels and statutory exceptions require independent review.'],
    }
    channels = attempt / 'channels'
    if channels.exists():
        raise ValueError('refusing to overwrite prior fire-lane channels')
    channels.mkdir()
    definitions = construction['recording_description']
    evidence = []
    for channel in definitions['channels']:
        name = channel['name']
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for row in original:
                values = {
                    'designation_and_posting': {
                        'designation_sha256': row['fire_code_designation_sha256'],
                        'posting_sha256': row['posting_authority_sha256'],
                        'sign_present': row['sign_physically_present']},
                    'curb_adjacency': max(0, min(row['body_east_x_m'], row['posted_interval_m'][1]) -
                                           max(row['body_west_x_m'], row['posted_interval_m'][0])),
                    'activity': row['activity_observation'],
                    'attendance': row['attended_observation'],
                    'property_status': row['property_kind'],
                    'necessity_exceptions': row['exception_kind'],
                }
                stream.write(json.dumps({'time_s': row['time_s'],
                                         'value': values[name]}) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': str(path.relative_to(attempt))})
    context = channels / 'context.json'
    context.write_text(json.dumps({'reviewed_fire_lane_packet': {
        'site_sha256': json.loads(required(attempt, 'original-attempt/inventory.json').read_text())['site_sha256'],
        'review_status': 'pending independent original-source review'}}) + '\n')
    for channel in definitions['context_inputs']:
        evidence.append({'name': channel['name'], 'unit': channel['unit'],
                         'reference': str(context.relative_to(attempt))})
    diagnostic = json.loads(required(attempt, 'original-attempt/inventory.json').read_text())['diagnostic_fixture']
    result = {
        'case_id': config['selected_case_id'],
        'measured_values': measurement['value'],
        'target_checks': [{'target': 'original body and activity within posted curb extent',
                           'requested': config['case'], 'measured': measurement['value'],
                           'method': 'measure_fire_lane', 'tolerance': 0,
                           'matched': True, 'physical_cause_confirmed': False,
                           'cause_evidence': measurement['sources']}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'Original physical and official-source review pending',
        'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in
                             ('overview', 'approach', 'reference_corner', 'driver_reference')],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': definitions,
        'recording_evidence': evidence, 'realized_observables': {},
        'provenance_kind': 'synthetic_fixture' if diagnostic else 'native',
        'diagnostic_fixture': diagnostic, 'physical_acceptance_claimed': False,
    }
    return report, result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report, result = build(args.attempt)
    from worker_exchange.native_output import write_result
    write_result(args.attempt, result)
    if args.output.exists():
        raise ValueError('refusing to overwrite prior fire-lane report')
    args.output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
