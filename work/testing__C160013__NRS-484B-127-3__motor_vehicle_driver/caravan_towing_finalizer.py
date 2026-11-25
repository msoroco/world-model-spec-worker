"""Saved-only C160013 towing result from source-hashed Native observations."""
import argparse
import hashlib
import json
from pathlib import Path

from caravan_towing_saved import CASE_ID, finalize as observe
from caravan_combination import analyze as analyze_combination
from caravan_spacing import analyze

CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')
SOURCES = ('config.json', 'road_context.json', 'caravan_context.json', 'site_packet.json',
           'caravan_history.jsonl', 'video_frames.jsonl', 'trace.jsonl',
           'capture/evidence.jsonl', 'towing-relationship.json',
           'towing_design_source.txt', *CAMERAS)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashed_context(report, context):
    return {'outside_business_district': context['outside_business_district'],
            'caravan_or_motorcade': context['caravan_or_motorcade'],
            'highway_id': context['highway_id'],
            'context_source_hashes': report['context_source_hashes']}


def source_hashed_body_gap(report):
    openings = [gap['longitudinal_opening_m'] for sample in report['samples']
                for gap in sample['gaps']]
    return {'minimum_opening_m': min(openings), 'maximum_opening_m': max(openings),
            'original_frames': len(report['samples'])}


def source_hashed_occupancy(report, saved):
    return {'entry_observed': bool(report['gap_occupancy']),
            'contact_frames': saved['contact_frames'],
            'without_danger_judgment': 'unresolved'}


def _channel(stream, name, rows, values, unit):
    path = stream / (name + '.jsonl')
    with path.open('x', encoding='utf-8') as output:
        for row, value in zip(rows, values):
            output.write(json.dumps({'original_frame': row['frame'],
                                     'time_s': row['time_s'], 'value': value},
                                    separators=(',', ':')) + '\n')
    return {'name': name, 'unit': unit, 'reference': 'channels/' + path.name}


def finalize(attempt, output):
    from worker_exchange.native_output import physical_result, write_result
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists() or (attempt / 'channels').exists():
        raise ValueError('Retain prior finalization; use a fresh attempt')
    for name in SOURCES:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text(encoding='utf-8'))
    case_id = config.get('selected_case_id')
    if case_id != CASE_ID:
        raise ValueError('Exact towing caravan case required')
    description = config.get('recording_description')
    if not isinstance(description, dict) or not description.get('channels'):
        raise ValueError('Selected recording description required')
    relationship = json.loads((attempt / 'towing-relationship.json').read_text(encoding='utf-8'))
    site_packet = json.loads((attempt / 'site_packet.json').read_text(encoding='utf-8'))
    design_ref = site_packet.get('towing_design_source')
    if not isinstance(design_ref, dict) or design_ref.get('path') != 'towing_design_source.txt':
        raise ValueError('Original towing design source reference required')
    design_hash = _sha(attempt / 'towing_design_source.txt')
    if design_ref.get('sha256') != design_hash or relationship.get('towing_design_source_sha256') != design_hash:
        raise ValueError('Changed original towing design source')
    drawing_id, drawn_id = relationship.get('drawing_actor_id'), relationship.get('drawn_actor_id')
    saved = observe(attempt, case_id, drawing_actor_id=drawing_id, drawn_actor_id=drawn_id)
    report = analyze(attempt)
    combination = analyze_combination(attempt, drawing_actor_id=drawing_id,
                                      drawn_actor_id=drawn_id)
    rows = [json.loads(line) for line in (attempt / 'caravan_history.jsonl').read_text(encoding='utf-8').splitlines()]
    if len(rows) != len(report['samples']):
        raise ValueError('Original caravan history/sample join failed')
    channel_dir = attempt / 'channels'
    channel_dir.mkdir()
    samples = report['samples']
    combination_samples = combination['samples']
    evidence = [
        _channel(channel_dir, 'caravan_member_bodies', rows,
                 [[member['body_vertices_xy_m'] for member in row['caravan_members']] for row in rows],
                 'polygon metres'),
        _channel(channel_dir, 'entering_vehicle_body', rows,
                 [row['entering_vehicle']['body_vertices_xy_m'] for row in rows],
                 'polygon metres'),
        _channel(channel_dir, 'inter_body_opening', rows,
                 [sample['gaps'][0]['longitudinal_opening_m'] for sample in samples], 'metres'),
        _channel(channel_dir, 'entrant_gap_occupancy', rows,
                 [sample['gaps'][0]['entering_body_wholly_between_member_bodies'] for sample in samples],
                 'boolean'),
        _channel(channel_dir, 'member_contact', rows,
                 [any(gap['entering_body_touches_member'] for gap in sample['gaps'])
                  for sample in samples], 'boolean'),
        _channel(channel_dir, 'drawn_unit_body', rows,
                 [row['drawn_units'][0]['body_vertices_xy_m'] for row in rows], 'polygon metres'),
        _channel(channel_dir, 'combination_gap_opening', rows,
                 [sample['following_gap_opening_m'] for sample in combination_samples], 'metres'),
    ]
    context = {'road_context': json.loads((attempt / 'road_context.json').read_text(encoding='utf-8'))}
    (channel_dir / 'road_context.json').write_text(json.dumps(context, indent=2) + '\n', encoding='utf-8')
    evidence.append({'name': 'road_context', 'unit': 'structured record',
                     'reference': 'channels/road_context.json'})
    expected = True
    observed = bool(saved['entry_observed'])
    check = {'target': 'original complete-body same-lane caravan gap occupancy',
             'requested': expected, 'measured': observed,
             'method': 'source-hashed complete bodies joined on 900 original 20 Hz frames',
             'tolerance': 0, 'matched': observed == expected,
             'physical_cause_confirmed': False,
             'cause_evidence': ['caravan_history.jsonl', 'video_frames.jsonl',
                                'road_context.json', 'site_packet.json']}
    result = {'case_id': case_id,
              'measured_values': {'entrant_gap_occupancy_observed': observed,
                                  'minimum_opening_m': saved['minimum_combination_gap_opening_m'],
                                  'member_contact_frames': saved['contact_frames']},
              'target_checks': [check],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'saved original-source analysis; physical and legal review separate',
              'physical_failure_flags': ['district, caravan and camera pixels require independent Native review',
                                         'without-danger judgment has no statutory numeric cutoff'],
              'trace_reference': 'trace.jsonl', 'video_references': list(CAMERAS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'source_evidence_hashes': {name: _sha(attempt / name) for name in SOURCES},
              'capture_evidence_sha256': _sha(attempt / 'capture/evidence.jsonl'),
              'realized_observables': {}}
    result = physical_result(attempt, result)
    source_hashes = {name: _sha(attempt / name) for name in SOURCES}
    def sources(*names):
        return {name: source_hashes[name] for name in names}
    analysis = {'format': 'worker-caravan-analysis', 'case_id': case_id,
                'measurements': {
                    'caravan_context': {'method': 'source_hashed_context',
                                        'value': source_hashed_context(report, context['road_context']),
                                        'sources': sources('road_context.json')},
                    'caravan_gap': {'method': 'source_hashed_body_gap',
                                    'value': {'minimum_combination_gap_opening_m': saved['minimum_combination_gap_opening_m'],
                                              'maximum_combination_length_m': saved['maximum_combination_length_m'],
                                              'original_frames': len(combination_samples)},
                                    'sources': sources('caravan_history.jsonl', 'video_frames.jsonl',
                                                       'towing-relationship.json')},
                    'caravan_entry': {'method': 'source_hashed_occupancy',
                                      'value': source_hashed_occupancy(report, saved),
                                      'sources': sources('road_context.json', 'caravan_history.jsonl',
                                                         'video_frames.jsonl')}},
                'source_report': saved, 'source_hashes': source_hashes,
                'physical_checks': result['physical_checks'],
                'legal_verdict_asserted': False}
    write_result(attempt, result)
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return analysis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)


if __name__ == '__main__':
    main()
