"""Audit exact C228508 comparisons on retained CPU diagnostic attempts.

This checks source joins, requested construction differences and comparison
isolation. Event labels remain hypotheses; no Native or legal outcome is claimed.
"""

import argparse
import ast
from hashlib import sha256
import json
from pathlib import Path

from following_comparison_audit import audit_pair, audit_speed_pair
from window_audit import audit as audit_window


HERE = Path(__file__).resolve().parent
HELD = ('law_id', 'cell_id', 'actor', 'rate_hz', 'frames', 'duration_s',
        'required_atoms', 'source_packets', 'cameras')
ORIGINALS = ('video_frames.jsonl', 'driving_trace.jsonl', 'following_sources.jsonl')
MILE_M = 1609.344


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()
            if line.strip()]


def event_rows(root):
    return json.loads((root / 'event_annotations.json').read_text())


def categories(rows):
    return [row['category'] for row in rows]


def request_span(root):
    tree = ast.parse((root / 'following_construction.py').read_text())
    phases = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                and target.id == 'PHASES' for target in node.targets):
            phases = node.value.elts
            break
    require(phases is not None, 'Missing source schedule')
    closings = []
    for phase in phases:
        require(isinstance(phase, ast.Call) and len(phase.args) >= 5,
                'Malformed source schedule')
        values = [ast.literal_eval(arg) for arg in phase.args[:5]]
        if 'closing_request' in values[4]:
            closings.append(values)
    require(len(closings) == 2, 'Two source closing requests required')
    return closings[1][1] - closings[0][0]


def joined_special(root, name, frames):
    path = root / name
    require(path.is_file(), 'Missing distinct source packet: ' + name)
    packet = lines(path)
    require(len(packet) == len(frames) and all(
        (row['frame'], row['time_s']) == (frame['carla_frame'], frame['time_s'])
        for row, frame in zip(packet, frames)), 'Distinct source/frame join differs: ' + name)
    require(all('synthetic' in row.get('source_scope', '') for row in packet),
            'Distinct CPU source lacks synthetic provenance: ' + name)
    return digest(path)


def audit(comparison_id, attempts):
    plan = json.loads((HERE / 'case-plan.json').read_text())
    selected = [row for row in plan['comparisons']
                if row['comparison_id'] == comparison_id]
    require(len(selected) == 1, 'Unknown or duplicate comparison')
    expected = selected[0]['case_ids']
    require(len(attempts) == len(expected), 'Exact comparison attempt count differs')
    roots = [Path(value) for value in attempts]
    configs = [json.loads((root / 'config.json').read_text()) for root in roots]
    require([row.get('selected_case_id') for row in configs] == expected,
            'Exact comparison attempt selects another case')
    for key in HELD:
        require(all(row.get(key) == configs[0].get(key) for row in configs[1:]),
                'Fixed construction changed: ' + key)
    sources = {}
    varied_following = {'immediate_hazard_required', 'following_hazard_required',
                        'any_sequence', 'following_any_sequence'}
    for name in ORIGINALS:
        values = [digest(root / name) for root in roots]
        if name == 'following_sources.jsonl' and comparison_id in varied_following:
            require(len(values) == 2 and values[0] != values[1],
                    'Requested diagnostic body-source variation missing')
            body = [lines(root / name) for root in roots]
            require(len(body[0]) == len(body[1]) and all(
                a['frame'] == b['frame'] and a['time_s'] == b['time_s'] and
                a['ego']['position_m'] == b['ego']['position_m'] and
                a['lead']['position_m'] == b['lead']['position_m']
                for a, b in zip(*body)), 'Diagnostic body source geometry changed')
            if 'hazard' in comparison_id:
                require(all(a['ego'] == b['ego'] and
                            a['lead']['speed_mps'] == 10 and
                            b['lead']['speed_mps'] == 12
                            for a, b in zip(*body)),
                        'Hazard guard body-source change differs')
            else:
                require(all(a['lead'] == b['lead'] and
                            b['ego']['speed_mps'] in (18, 24)
                            for a, b in zip(*body)) and
                        body[1][0]['ego']['speed_mps'] == 18 and
                        body[1][-1]['ego']['speed_mps'] == 24,
                        'Reversed sequence body-source change differs')
            sources[name] = values
        else:
            require(len(set(values)) == 1, 'Fixed original source changed: ' + name)
            sources[name] = values[0]
    reports = [audit_window(root, root / 'analysis-report.json') for root in roots]
    events = [event_rows(root) for root in roots]
    frames = [lines(root / 'video_frames.jsonl') for root in roots]
    for source, frame_map in zip(events, frames):
        valid = {row['carla_frame'] for row in frame_map}
        require(all(row['frame'] in valid for row in source),
                'Event hypothesis lacks original frame')
    names = [row.rsplit('__', 1)[-1] for row in expected]
    observed = {}
    if comparison_id in ('two_acts_required', 'repeated_following_vs_single'):
        observed = audit_pair(*roots)
    elif comparison_id == 'speed_required':
        observed = audit_speed_pair(*roots)
    elif comparison_id == 'different_vs_repeated':
        require(categories(events[0]).count('device') == 1 and
                'marked_lane' in categories(events[0]) and
                categories(events[1]).count('device') == 2 and
                'marked_lane' not in categories(events[1]),
                'Distinct versus repeated predicate sources differ incorrectly')
    elif comparison_id in ('immediate_hazard_required', 'following_hazard_required'):
        require('hazard' in categories(events[0]) and
                'hazard' not in categories(events[1]) and
                configs[1].get('engineering', {}).get('hazard_guard_ttc_s') == 3.0,
                'Hazard-guard construction or event hypothesis differs incorrectly')
    elif comparison_id == 'hazard_target':
        targets = [[row.get('target_type') for row in source if row['category'] == 'hazard']
                   for source in events]
        require(targets == [['vehicle'], ['person']], 'Hazard target source differs incorrectly')
    elif comparison_id in ('one_mile_window', 'following_one_mile_window'):
        spans = [request_span(root) for root in roots]
        if comparison_id == 'one_mile_window':
            require(len(spans) == 3 and spans[0] < MILE_M and
                    spans[1] > MILE_M and abs(spans[2] - MILE_M) < 1e-6,
                    'Below/at/above source request spans differ incorrectly')
        else:
            require(spans[0] < MILE_M and spans[1] > MILE_M,
                    'Following source request spans differ incorrectly')
        observed['requested_span_m'] = spans
    elif comparison_id == 'listed_off_pavement':
        observed['right_pass_source_sha256'] = joined_special(
            roots[1], 'right_pass_sources.jsonl', frames[1])
        require(not (roots[0] / 'right_pass_sources.jsonl').exists() and
                'right_pass_construction' in (roots[1] / 'runner.py').read_text(),
                'Right-pass construction is not isolated')
    elif comparison_id == 'listed_following':
        engineering = configs[1].get('engineering', {})
        require((engineering.get('lead_spawn_station_m'),
                 engineering.get('closing_lead_speed_mps')) == (25, 7) and
                'lead_spawn_station_m' not in configs[0].get('engineering', {}) and
                categories(events[1]).count('too_close') == 2,
                'Following geometry request is not isolated')
    elif comparison_id == 'listed_yield':
        observed['yield_source_sha256'] = joined_special(
            roots[1], 'yield_sources.jsonl', frames[1])
        require(not (roots[0] / 'yield_sources.jsonl').exists() and
                'yield_construction' in (roots[1] / 'runner.py').read_text(),
                'Yield construction is not isolated')
    elif comparison_id in ('any_sequence', 'following_any_sequence'):
        def order(source):
            speed = [row['frame'] for row in source if row['category'] == 'speed']
            closings = [row['frame'] for row in source if row['category'] == 'too_close']
            require(len(speed) == 1 and len(closings) == 2,
                    'Sequence event sources incomplete')
            return speed[0] < min(closings), speed[0] > max(closings)
        require(order(events[0])[0] and order(events[1])[1] and
                configs[1].get('engineering', {}).get('early_speed_cap_mps') == 18,
                'Reversed source request sequence differs incorrectly')
    else:
        raise ValueError('No independent comparison audit for ' + comparison_id)
    return {'format': 'worker-current-comparison-dispatch-audit',
            'comparison_id': comparison_id, 'case_ids': expected,
            'case_suffixes': names, 'fixed_original_sha256': sources,
            'analysis_report_sha256': [digest(root / 'analysis-report.json') for root in roots],
            'event_source_sha256': [digest(root / 'event_annotations.json') for root in roots],
            'observed_source_difference': observed,
            'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--attempt', action='append', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.comparison, args.attempt)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(args.comparison, 'current_source_comparison_passed',
          'physical_and_legal_acceptance_unclaimed')
