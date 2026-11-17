"""Independent, source-bound comparison of C150142 observations.

This checks declared fixed facts and the intended difference. It does not decide
whether a statutory exception applies or whether synthetic media is physical proof.
"""
import argparse
import hashlib
import json
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_fact(root, binding, case_id, source_kind):
    require(isinstance(binding, dict) and set(binding) ==
            {'path', 'sha256', 'pointer'}, 'Invalid fact binding')
    rel = binding['path']
    require(isinstance(rel, str) and rel and not Path(rel).is_absolute() and
            '..' not in Path(rel).parts, 'Unsafe fact path')
    path = (root / rel).resolve()
    require(path.is_relative_to(root.resolve()) and path.is_file(),
            'Missing fact source: ' + rel)
    require(file_sha256(path) == binding['sha256'], 'Stale fact source: ' + rel)
    data = json.loads(path.read_text())
    require(data.get('case_id') == case_id and
            data.get('source_kind') == source_kind,
            'Fact source identity/provenance mismatch: ' + rel)
    pointer = binding['pointer']
    require(isinstance(pointer, str) and pointer.startswith('/'),
            'Invalid fact pointer')
    for raw in pointer[1:].split('/'):
        key = raw.replace('~1', '/').replace('~0', '~')
        require(isinstance(data, dict) and key in data,
                'Missing source fact: ' + pointer)
        data = data[key]
    require(data is not None, 'Empty source fact: ' + pointer)
    return data


def audit(plan, bundle, root, comparison_id, allow_synthetic=False):
    comparisons = [c for c in plan['comparisons']
                   if c['comparison_id'] == comparison_id]
    require(len(comparisons) == 1, 'Unknown comparison')
    comparison = comparisons[0]
    cases = comparison['case_ids']
    require(len(cases) >= 2 and len(set(cases)) == len(cases),
            'Invalid comparison cases')
    require(bundle.get('format') == 'c150142-source-comparison-v1' and
            bundle.get('comparison_id') == comparison_id and
            set(bundle.get('cases', {})) == set(cases),
            'Comparison bundle does not match case plan')
    fixed = comparison['fixed_conditions']
    varied = comparison['deliberate_differences']
    require(fixed and varied and not set(fixed) & set(varied),
            'Invalid fixed/varied dimensions')
    observed = {}
    for case_id in cases:
        row = bundle['cases'][case_id]
        kind = row.get('source_kind')
        require(kind == 'original_native' or
                (allow_synthetic and kind == 'synthetic_native_sample'),
                'Comparison requires original Native provenance')
        require(set(row.get('facts', {})) == set(fixed) | set(varied),
                'Missing or extra comparison fact: ' + case_id)
        values = {name: resolve_fact(root, binding, case_id, kind)
                  for name, binding in row['facts'].items()}
        require(values.get('cell', 'C150142') == 'C150142',
                'Wrong comparison cell')
        observed[case_id] = values
    for name in fixed:
        values = [observed[c][name] for c in cases]
        require(all(v == values[0] for v in values[1:]),
                'Fixed condition changed: ' + name)
    for name in varied:
        values = [observed[c][name] for c in cases]
        require(len({json.dumps(v, sort_keys=True) for v in values}) > 1,
                'Declared difference absent: ' + name)
        if name == 'stationary_duration_s':
            require(len(cases) == 3 and
                    type(values[0]) in (int, float) and values[0] < 1800 and
                    values[1] == 1800 and
                    type(values[2]) in (int, float) and values[2] > 1800,
                    '30-minute boundary observations missing below/at/above')
        elif name.endswith('_event') or name in ('sign_present',
                                                  'mailbox_presence',
                                                  'red_curb_stop_or_park'):
            require(all(type(v) is bool for v in values),
                    'Boolean comparison fact has wrong type: ' + name)
    return {'format': 'c150142-comparison-audit-v1',
            'comparison_id': comparison_id, 'case_ids': cases,
            'source_kinds': [bundle['cases'][c]['source_kind'] for c in cases],
            'fixed_conditions_checked': fixed, 'differences_checked': varied,
            'physical_acceptance_claimed': False, 'legal_verdict': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--allow-synthetic-diagnostic', action='store_true')
    args = parser.parse_args()
    plan = json.loads(Path(args.plan).read_text())
    bundle_path = Path(args.bundle).resolve()
    bundle = json.loads(bundle_path.read_text())
    result = audit(plan, bundle, bundle_path.parent, args.comparison,
                   args.allow_synthetic_diagnostic)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
