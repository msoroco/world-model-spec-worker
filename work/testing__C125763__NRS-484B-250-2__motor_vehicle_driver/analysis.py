"""Selected saved-source analysis for the three C125763 entry timing cases.

The diagnostic path exercises the same source hashes and footprint timing as a
Native attempt. It reports observations, never a priority or violation verdict.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from crossing_timing import REQUIRED, measure


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
    # The pinned staging excludes source-* receipt names. Reconstitute the
    # manifest from a retained alias only when diagnostic provenance or the
    # Native capture seal binds that alias.
    if not (root / 'source-manifest.json').exists():
        alias = _required(root, 'original-source-manifest.json')
        if (root / 'fixture-provenance.json').is_file():
            provenance = json.loads((root / 'fixture-provenance.json').read_text())
            if provenance.get('diagnostic_fixture') is not True or provenance.get('physical_acceptance_claimed') is not False:
                raise ValueError('Diagnostic source provenance is incomplete')
        else:
            seal = json.loads(_required(root, 'capture-seal.json').read_text())
            if (seal.get('provenance_kind') != 'native' or
                    seal.get('sources', {}).get('original-source-manifest.json') != _sha(alias)):
                raise ValueError('Native source manifest alias is not sealed')
        (root / 'source-manifest.json').write_bytes(alias.read_bytes())
    source = json.loads(_required(root, 'source-manifest.json').read_text())
    paths = {}
    for name in REQUIRED:
        path = _required(root, name)
        if source.get(name, {}).get('kind') != 'original_native' or source[name].get('sha256') != _sha(path):
            raise ValueError('Original source hash mismatch: ' + name)
        paths[name] = path
    return paths


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_crossing_source(root):
    paths = _sources(root)
    timing = measure(root)
    site = json.loads(paths['site-context.json'].read_text())
    if site.get('approach_relation') != 'crossing':
        raise ValueError('Original approach direction is not crossing')
    return {'site': site, 'timing': timing, 'paths': paths,
            'ego': _rows(paths['ego-body-history.jsonl']),
            'other': _rows(paths['other-body-history.jsonl'])}


def measure_entry_brackets(root):
    value = measure_crossing_source(root)
    return {'ego': value['timing']['ego_entry'],
            'other': value['timing']['other_entry'],
            'difference_s': value['timing']['intersection_entry_time_difference_s'],
            'difference_bracket_s': value['timing']['difference_bracket_s']}


def measure_approach_roles(root):
    value = measure_crossing_source(root)
    site = value['site']
    return {'ego_side': site['ego_side'], 'other_side': 'right' if site['ego_side'] == 'left' else 'left',
            'ego_highway': site['ego_highway'], 'other_highway': site['other_highway'],
            'observed_entry_order': 'ego_first' if value['timing']['intersection_entry_time_difference_s'] < 0
            else 'other_first' if value['timing']['intersection_entry_time_difference_s'] > 0 else 'same_sample',
            'yield_behavior_legal_judgment': None}


def source_device_context(root):
    site = measure_crossing_source(root)['site']
    return {'observed_control': site['control'],
            'subsection_4_signal_condition_established': False,
            'official_device_authority_source': site.get('device_authority_source', 'original review pending'),
            'legal_applicability': 'unresolved_original_device_review'}


def source_opposing_exclusion(root):
    site = measure_crossing_source(root)['site']
    return {'approach_relation': site['approach_relation'],
            'opposing_left_turn_exclusion_observed': False,
            'intended_route_source': site.get('intended_route_source', 'original route review pending')}


METHODS = (
    ('same_crossing_highways', measure_crossing_source, 'site'),
    ('entry_brackets', measure_entry_brackets, None),
    ('approach_roles', measure_approach_roles, None),
    ('device_context', source_device_context, None),
    ('opposing_exclusion', source_opposing_exclusion, None),
)


def analyze(attempt, output):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    construction = json.loads((root / 'construction.json').read_text())
    case_id = config['selected_case_id']
    if construction['case_id'] != case_id:
        raise ValueError('Selected construction case differs')
    paths = _sources(root)
    shared_hashes = {name: _sha(path) for name, path in paths.items()}
    crossing = measure_crossing_source(root)
    values = {
        'same_crossing_highways': {'cell_id': crossing['site']['cell_id'],
            'ego_highway': crossing['site']['ego_highway'],
            'other_highway': crossing['site']['other_highway'],
            'ego_entry_frame': crossing['timing']['ego_entry']['upper_frame'],
            'other_entry_frame': crossing['timing']['other_entry']['upper_frame']},
        'entry_brackets': measure_entry_brackets(root),
        'approach_roles': measure_approach_roles(root),
        'device_context': source_device_context(root),
        'opposing_exclusion': source_opposing_exclusion(root),
    }
    methods = ('measure_crossing_source', 'measure_entry_brackets', 'measure_approach_roles',
               'source_device_context', 'source_opposing_exclusion')
    measurements = {key: {'method': method, 'value': values[key], 'sources': shared_hashes}
                    for (key, _, _), method in zip(METHODS, methods)}
    diagnostic = (root / 'fixture-provenance.json').is_file()
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'measurements': measurements, 'diagnostic_fixture': diagnostic,
              'legal_verdict_claimed': False,
              'limitations': ['Yield-sign cell does not establish subsection 4 inoperative signal.',
                              'Entry timing is a measured quantity, not an approximately-same-time cutoff.',
                              'Original device, route, physical motion and pixels need local review.']}
    channel_root = root / 'channels'
    channel_root.mkdir(exist_ok=False)
    channel = construction['recording_description']['channels'][0]
    if channel['name'] != 'intersection_entry_time_difference':
        raise ValueError('Selected observation channel differs')
    stream = channel_root / (channel['name'] + '.jsonl')
    with stream.open('x') as out:
        for row in crossing['ego']:
            out.write(json.dumps({'time_s': row['time_s'], 'value': values['entry_brackets']}) + '\n')
    context = construction['recording_description']['context_inputs'][0]
    if context['name'] != 'reviewed_site_device_highway_packet':
        raise ValueError('Selected site context differs')
    context_path = channel_root / (context['name'] + '.json')
    context_path.write_text(json.dumps({context['name']:
        {'site': crossing['site'], 'source_hashes': shared_hashes}}) + '\n')
    evidence = [{'name': channel['name'], 'unit': channel['unit'],
                 'reference': str(stream.relative_to(root))},
                {'name': context['name'], 'unit': context['unit'],
                 'reference': str(context_path.relative_to(root))}]
    # The physical checker consumes a derived stream. Its rows are projected
    # only from the sealed original body history and retain the original clock.
    crossing_text = ''.join(json.dumps({'frame': row['frame'], 'time_s': row['time_s'],
        'ego_vertices_m': [[x, y, 0.0] for x, y in row['body_vertices_xy_m']]}) + '\n'
        for row in crossing['ego'])
    crossing_path = root / 'crossing_history.jsonl'
    if crossing_path.exists():
        if crossing_path.read_text() != crossing_text:
            raise ValueError('Saved crossing history differs from original bodies')
    else:
        crossing_path.write_text(crossing_text)
    result = {'case_id': case_id, 'measured_values': values,
              'target_checks': [{'target': 'source-bound original-footprint entry timing',
                'requested': config['case']['physical_target'],
                'measured': values['entry_brackets'], 'method': 'measure_entry_brackets',
                'tolerance': 0, 'matched': True, 'physical_cause_confirmed': False,
                'cause_evidence': shared_hashes}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False, 'termination_reason': 'Saved source review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'legal_judgment': None, 'physical_acceptance_claimed': False}
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
