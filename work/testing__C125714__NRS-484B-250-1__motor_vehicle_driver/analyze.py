"""Saved full-footprint entry timing, yield response, and follow-up decision."""
import argparse
from native_finalize import finalize
import json
from pathlib import Path
from source_audit import audit_sources
from scenario import route


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
    precedence = None if ego is None or other is None else other[1] < ego[0]
    yielding = any(x['controller']['yield_requested'] for x in rows)
    completed = rows and rows[-1]['controller']['ego_index'] >= len(route('ego'))-2
    branch = cfg['case']['variable_assignments']['test_branch']['value']
    measured = {'entry_brackets_s': {'ego': ego, 'other': other},
                'other_enters_before_ego': precedence, 'yield_control_requested': yielding,
                'ego_route_completed': bool(completed)}
    need_repair = precedence is not True or not completed or (branch == 'prior_entry_yield' and not yielding)
    return {'format': 'prior-entry-capability-v1', 'case_id': cfg['selected_case_id'],
            'original_source_validation': sources,
            'measurements': measured, 'decision': 'repair_same_frozen_case' if need_repair else 'inspect_native_capture',
            'follow_up_configuration': {'source': 'config.json', 'case_id': cfg['selected_case_id'],
                                        'target_settings_preserved': True, 'new_attempt_required': need_repair},
            'physical_acceptance': False,
            'unverified': ['roadway intersection status', 'public access', 'native physical geometry',
                           'camera visibility', 'mandatory source and final video validation']}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--attempt', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    report = assess(a.attempt)
    Path(a.output).write_text(json.dumps(report, indent=2) + '\n')
    finalize(a.attempt, report)
