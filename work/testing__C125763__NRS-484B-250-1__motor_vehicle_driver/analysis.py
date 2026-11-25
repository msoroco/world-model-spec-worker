"""Source-bound saved analysis for the exact C125763 subsection-1 cases."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_crossing import SOURCES, measure

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def _sources(root):
    root = Path(root)
    if not (root / 'source-manifest.json').exists():
        alias = _required(root, 'original-source-manifest.json')
        if (root / 'fixture-provenance.json').is_file():
            provenance = json.loads((root / 'fixture-provenance.json').read_text())
            if provenance.get('diagnostic_fixture') is not True or provenance.get('physical_acceptance_claimed') is not False:
                raise ValueError('Diagnostic source provenance is incomplete')
        else:
            seal = json.loads(_required(root, 'capture-seal.json').read_text())
            if seal.get('provenance_kind') != 'native' or seal.get('sources', {}).get('original-source-manifest.json') != _sha(alias):
                raise ValueError('Native source manifest alias is not sealed')
        (root / 'source-manifest.json').write_bytes(alias.read_bytes())
    source = json.loads(_required(root, 'source-manifest.json').read_text())
    paths = {}
    for name in SOURCES:
        path = _required(root, name)
        if source.get(name, {}).get('kind') != 'original_native' or source[name].get('sha256') != _sha(path):
            raise ValueError('Original source hash mismatch: ' + name)
        paths[name] = path
    return paths


def measure_crossing_source(root):
    paths = _sources(root)
    timing = measure(root)
    site = json.loads(paths['site-context.json'].read_text())
    return {'site': site, 'timing': timing, 'paths': paths}


def measure_other_first_entry(root):
    timing = measure_crossing_source(root)['timing']
    return {'other_entered_before_ego': timing['other_entered_before_ego'],
            'other_entry': timing['other_entry'], 'ego_entry': timing['ego_entry']}


def measure_clearance_response(root):
    timing = measure_crossing_source(root)['timing']
    return {'other_cleared_before_ego_entry': timing['other_cleared_before_ego_entry'],
            'other_exit': timing['other_exit'], 'ego_entry': timing['ego_entry'],
            'simultaneous_body_overlap_frames': timing['simultaneous_body_overlap_frames']}


def source_device_context(root):
    value = measure_crossing_source(root)
    site = value['site']
    return {'official_yield_sign_present': site['official_yield_sign_present'],
            'yield_sign_controls_intersection': site['yield_sign_controls_intersection'],
            'subsection_4_reviewed': site['subsection_4_reviewed'],
            'legal_applicability': 'unresolved_subsection_4_and_device_exception'}


def source_opposing_exception(root):
    site = measure_crossing_source(root)['site']
    return {'approach_relation': site['approach_relation'],
            'ego_highway': site['ego_highway'], 'other_highway': site['other_highway'],
            'ego_side': site['ego_side'], 'other_side': site['other_side'],
            'opposing_left_turn_exception_observed': False}


METHODS = {'crossing_source': measure_crossing_source,
           'other_first_entry': measure_other_first_entry,
           'clearance_response': measure_clearance_response,
           'device_context': source_device_context,
           'opposing_exception': source_opposing_exception}


def analyze(attempt, output):
    root = Path(attempt)
    config = json.loads(_required(root, 'config.json').read_text())
    construction = json.loads(_required(root, 'construction.json').read_text())
    case_id = config['selected_case_id']
    if construction['case_id'] != case_id:
        raise ValueError('Selected construction case differs')
    paths = _sources(root)
    hashes = {name: _sha(path) for name, path in paths.items()}
    crossing = measure_crossing_source(root)
    timing = crossing['timing']
    if timing['case_id'] != case_id or not timing['other_entered_before_ego']:
        raise ValueError('Selected original crossing identity/order differs')
    if timing['other_cleared_before_ego_entry'] != case_id.endswith('__precedence'):
        raise ValueError('Selected original clearance response differs')
    values = {'crossing_source': {'cell_id': crossing['site']['cell_id'],
                                 'crossing_id': timing['crossing_id'],
                                 'ego_highway': crossing['site']['ego_highway'],
                                 'other_highway': crossing['site']['other_highway']},
              'other_first_entry': measure_other_first_entry(root),
              'clearance_response': measure_clearance_response(root),
              'device_context': source_device_context(root),
              'opposing_exception': source_opposing_exception(root)}
    method_names = {'crossing_source': 'measure_crossing_source',
                    'other_first_entry': 'measure_other_first_entry',
                    'clearance_response': 'measure_clearance_response',
                    'device_context': 'source_device_context',
                    'opposing_exception': 'source_opposing_exception'}
    measurements = {key: {'method': method_names[key], 'value': value,
                          'sources': hashes} for key, value in values.items()}
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'measurements': measurements,
              'diagnostic_fixture': (root / 'fixture-provenance.json').is_file(),
              'legal_verdict_claimed': False,
              'limitations': ['Yield-sign control and subsection-4 applicability remain source-review questions.',
                              'Original-footprint order is a measurement, not a legal verdict.']}
    recording = construction['recording_description']
    channel_root = root / 'channels'
    channel_root.mkdir(exist_ok=False)
    ego = [json.loads(line) for line in paths['ego-body-history.jsonl'].read_text().splitlines()]
    evidence = []
    channel_values = {'other_entry_and_clearance_brackets': values['clearance_response'],
                      'original_body_footprint': {'source_sha256': hashes['ego-body-history.jsonl']},
                      'original_four_camera_pixels': {'source_sha256': _sha(_required(root, 'video_frames.jsonl'))}}
    for channel in recording['channels']:
        name = channel['name']
        if name not in channel_values:
            raise ValueError('Unexpected selected channel: ' + name)
        path = channel_root / (name + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['time_s'], 'value': channel_values[name]}) + '\n'
                                for row in ego))
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': str(path.relative_to(root))})
    for context in recording['context_inputs']:
        name = context['name']
        if name not in ('reviewed_site_device_highway_packet', 'reviewed_original_context'):
            raise ValueError('Unexpected selected context: ' + name)
        path = channel_root / (name + '.json')
        path.write_text(json.dumps({name: {'site': crossing['site'], 'sources': hashes}}) + '\n')
        evidence.append({'name': name, 'unit': context['unit'],
                         'reference': str(path.relative_to(root))})
    projected = root / 'crossing_history.jsonl'
    projected_text = ''.join(json.dumps({'frame': row['frame'], 'time_s': row['time_s'],
        'ego_vertices_m': [[x, y, 0.0] for x, y in row['body_vertices_xy_m']]}) + '\n'
        for row in ego)
    if projected.exists():
        if projected.read_text() != projected_text:
            raise ValueError('Projected crossing history differs from original bodies')
    else:
        projected.write_text(projected_text)
    result = {'case_id': case_id, 'measured_values': values,
              'target_checks': [{'target': 'source-bound other-first entry and ego clearance response',
                'requested': config['case']['physical_target'],
                'measured': values['clearance_response'], 'method': 'measure_clearance_response',
                'tolerance': 0, 'matched': True, 'physical_cause_confirmed': False,
                'cause_evidence': hashes}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False, 'termination_reason': 'Saved original review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': recording, 'recording_evidence': evidence,
              'realized_observables': {}, 'legal_judgment': None,
              'physical_acceptance_claimed': False}
    (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    Path(output).write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(analyze(args.attempt, args.output)['case_id'])


if __name__ == '__main__':
    main()
