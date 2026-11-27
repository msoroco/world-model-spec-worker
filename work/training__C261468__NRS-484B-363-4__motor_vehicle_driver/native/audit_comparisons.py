"""Independent exact-source comparison isolation audit, diagnostic only."""
import argparse
import hashlib
import json
from pathlib import Path

ALLOWED = {
    'school_session': {'pupils_in_class', 'school_in_session'},
    'after_end_30min': {'operation_end_unix_s'},
    'before_start_30min': {'next_operation_start_unix_s'},
    'class_beacon_state': {'beacon_lamps_sha256'},
    'nonbeacon_sign_state': {'sign_says_limit_in_effect'},
    'zone_kind': {'zone_kind'},
}


def require(ok, why):
    if not ok:
        raise ValueError(why)


def run(folder, comparison_id, inject=False):
    folder = Path(folder)
    plan = json.loads((folder / 'case-plan.json').read_text())
    matching = [x for x in plan['comparisons'] if x['comparison_id'] == comparison_id]
    require(len(matching) == 1, 'Unknown exact comparison')
    comparison = matching[0]
    slug = comparison_id.split('__')[-1]
    expected = ALLOWED[slug]
    contexts = []
    traces = []
    for case_id in comparison['case_ids']:
        sub = folder / 'diagnostic' / case_id.split('__')[-1]
        contexts.append(json.loads((sub / 'school_zone_context.json').read_text()))
        traces.append(hashlib.sha256((folder / 'diagnostic/common/pass_trace.jsonl').read_bytes()).hexdigest())
    if inject:
        contexts[-1]['route_direction_id'] = 'unexpected_route'
    differences = {key for context in contexts[1:] for key in contexts[0]
                   if context.get(key) != contexts[0].get(key)}
    require(differences == expected, 'Unlisted source-condition difference: ' +
            ','.join(sorted(differences ^ expected)))
    require(len(set(traces)) == 1, 'Participant source motion differs')
    require(all(x['zone_sign_source'] == 'synthetic source only' and
                x['zone_boundary_source'] == 'synthetic source only' for x in contexts),
            'Diagnostic context misrepresented as original source')
    return {'comparison_id': comparison_id, 'case_ids': comparison['case_ids'],
            'diagnostic_only': True, 'fixed_source_motion_sha256': traces[0],
            'source_differences': sorted(differences), 'original_source_review': 'pending'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', required=True)
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--inject-unlisted-difference', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(args.folder, args.comparison, args.inject_unlisted_difference),
                     sort_keys=True))
