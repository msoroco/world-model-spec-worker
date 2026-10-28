"""Measure actual crossing-entry difference without deciding 'approximately'."""
import argparse
import json
from pathlib import Path

from scenario import route
from source_audit import audit_sources


def bracket(rows, role):
    for before, after in zip(rows, rows[1:]):
        if not before[role]['inside_crossing'] and after[role]['inside_crossing']:
            return [before['time_s'], after['time_s']]
    return None


def assess(attempt):
    attempt = Path(attempt)
    cfg = json.loads((attempt / 'config.json').read_text())
    rows = [json.loads(x) for x in (attempt / 'participants.jsonl').read_text().splitlines()]
    sources = audit_sources(attempt, cfg, rows)
    ego, other = bracket(rows, 'ego'), bracket(rows, 'other')
    difference = None if ego is None or other is None else [ego[0] - other[1], ego[1] - other[0]]
    midpoint = None if ego is None or other is None else ((ego[0]+ego[1])-(other[0]+other[1]))/2
    completed = bool(rows and rows[-1]['controller']['ego_index'] >= len(route('ego'))-2 and
                     rows[-1]['controller']['other_index'] >= len(route('other'))-2)
    return {'format': 'same-time-crossing-capability-v1', 'case_id': cfg['selected_case_id'],
            'original_source_validation': sources,
            'requested_release_delay_s': cfg['case']['variable_assignments']['commanded_release_delay_s']['value'],
            'entry_brackets_s': {'ego': ego, 'other': other},
            'measured_entry_difference_bracket_s': difference,
            'entry_time_difference_s': midpoint,
            'both_routes_completed': completed, 'judgment_resolved': False,
            'decision': 'inspect_frozen_sweep_evidence' if difference is not None and completed else 'repair_same_frozen_case',
            'follow_up_configuration': {'source': 'config.json', 'case_id': cfg['selected_case_id'],
                                        'preserve_release_delay': True, 'new_attempt_required': not completed},
            'physical_acceptance': False,
            'unverified': ['native intersection geometry', 'right-side relationship', 'camera visibility',
                           'mandatory capture coverage', 'encoded video validity']}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--attempt', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    Path(a.output).write_text(json.dumps(assess(a.attempt), indent=2) + '\n')
