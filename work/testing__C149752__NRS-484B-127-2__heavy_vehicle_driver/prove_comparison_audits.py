"""Independent diagnostic source comparison with source-tamper and omission tests."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import gap_comparison_audit
import overtaking_comparison_audit
import lane_comparison_audit
import width_comparison_audit

MODULES = {
    'following_gap_boundary': gap_comparison_audit,
    'overtaking_permission': overtaking_comparison_audit,
    'same_direction_lane_exclusion': lane_comparison_audit,
    'ego_overall_width_80in_boundary': width_comparison_audit,
    'lead_overall_width_80in_boundary': width_comparison_audit,
}
FILES = ('config.json', 'result.json', 'analysis-report.json', 'road_context.json',
         'truck_history.jsonl', 'video_frames.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove(manifest, comparison, work_root):
    folder = Path(manifest).resolve().parent
    entries = json.loads(Path(manifest).read_text())['cases']
    plan = json.loads((folder/'case-plan.json').read_text())
    spec = next(row for row in plan['comparisons'] if row['comparison_id'] == comparison)
    module = MODULES[comparison]
    suffixes = module.CASES if hasattr(module, 'CASES') else tuple(module.GAPS)
    by_suffix = {row['case_id'].split('__')[-1]: row for row in entries}
    paths = {}
    for suffix in suffixes:
        row = by_suffix[suffix]
        saved = json.loads((folder/row['post_capture']['receipt']).read_text())
        paths[suffix] = Path(saved['analysis_directory'])
    positive = module.audit(paths)
    if positive.get('passed') is not True or not set(spec['case_ids']) <= set(positive['case_ids']):
        raise ValueError('Comparison did not cover planned exact cases')
    chosen = 'lead_width_below_80in' if comparison == 'lead_overall_width_80in_boundary' else suffixes[1]
    changed_role = 'lead' if comparison == 'lead_overall_width_80in_boundary' else 'ego'
    with tempfile.TemporaryDirectory(prefix='c149752-comparison-', dir=work_root) as temp:
        changed = Path(temp)
        for name in FILES:
            shutil.copyfile(paths[chosen]/name, changed/name)
        rows = [json.loads(line) for line in (changed/'truck_history.jsonl').read_text().splitlines()]
        for row in rows:
            row[changed_role]['overall_width_m'] = float(row[changed_role]['overall_width_m']) + .6
        (changed/'truck_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
        report = json.loads((changed/'analysis-report.json').read_text())
        for measurement in report['measurements'].values():
            if isinstance(measurement, dict) and 'sources' in measurement and 'truck_history.jsonl' in measurement['sources']:
                measurement['sources']['truck_history.jsonl'] = sha(changed/'truck_history.jsonl')
        if 'minimum_overall_width_m' in report['measurements']:
            report['measurements']['minimum_overall_width_m']['value'][changed_role] += .6
        (changed/'analysis-report.json').write_text(json.dumps(report)+'\n')
        altered = dict(paths, **{chosen: changed})
        try:
            module.audit(altered)
        except ValueError as error:
            changed_error = str(error)
        else:
            raise ValueError('Altered original truck width was accepted')
        (changed/'truck_history.jsonl').unlink()
        try:
            module.audit(altered)
        except (ValueError, FileNotFoundError) as error:
            missing_error = str(error)
        else:
            raise ValueError('Missing original truck history was accepted')
    return {'format': 'worker-comparison-diagnostic-proof', 'comparison_id': comparison,
            'passed': True, 'physical_acceptance_claimed': False,
            'case_ids': spec['case_ids'], 'audited_case_ids': positive['case_ids'],
            'positive': positive, 'changed_width_rejection': changed_error,
            'missing_history_rejection': missing_error,
            'source_sha256': {suffix: {name: sha(path/name) for name in FILES}
                              for suffix, path in paths.items()},
            'scope': 'synthetic saved-source software comparison; legal and physical status unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--comparison', choices=tuple(MODULES), required=True)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.work_root.mkdir(parents=True, exist_ok=True)
    result = prove(args.manifest, args.comparison, args.work_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'comparison_id': args.comparison, 'passed': True,
                      'changed_width_rejection': result['changed_width_rejection'],
                      'missing_history_rejection': result['missing_history_rejection']}, sort_keys=True))


if __name__ == '__main__':
    main()
