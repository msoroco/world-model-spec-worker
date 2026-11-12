"""Audit seven full-duration source comparisons against draft constructions."""
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from comparison_audit import audit_pair


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(case_id):
    label = case_id.rsplit('source_verified_', 1)[1]
    version = 'v2' if label == 'faster_ego' else 'v1'
    path = REPO / '.runtime-work/c101303-full-duration' / (
        label + '-positive-' + version + '/attempt/vehicle_history.jsonl')
    receipt = json.loads((ROOT / 'delivery-proofs' / label / 'diagnostic-audit.json').read_text())
    if (receipt['frames'] != 900 or receipt['passed'] is not False
            or receipt['original_sources']['history_sha256'] != digest(path)):
        raise ValueError('Comparison source lacks sealed diagnostic join: ' + case_id)
    return path


def main():
    manifest_path = ROOT / 'body-geometry-all-draft-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    if len(plan['comparisons']) != 7:
        raise ValueError('Expected seven controlled primary comparisons')
    with tempfile.TemporaryDirectory(prefix='c101303-geometry-comparison-',
                                     dir=REPO / '.runtime-work') as temporary:
        context = Path(temporary)
        shutil.copyfile(manifest_path, context / 'execution-manifest.json')
        shutil.copyfile(plan_path, context / 'case-plan.json')
        for case in manifest['cases']:
            for row in [case] + case['candidates']:
                original = ROOT / row['construction']
                if digest(original) != row['construction_sha256']:
                    raise ValueError('Draft construction changed: ' + str(original))
                target = context / row['construction']
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, target)
        results = []
        for pair in plan['comparisons']:
            left, right = map(source, pair['case_ids'])
            result = audit_pair(context, pair['comparison_id'], left, right)
            if result['frames'] != 900:
                raise ValueError('Primary comparison lacks full duration')
            results.append(result)
            print(pair['comparison_id'], result['frames'], flush=True)
        gap_pair = next(row for row in plan['comparisons']
                        if row['comparison_id'] == 'body_gap')
        left, right = map(source, gap_pair['case_ids'])
        rows = [json.loads(line) for line in left.read_text().splitlines()]
        rows[0]['surface_condition'] = 'synthetic_condition_tamper'
        negative = context / 'negative-surface.jsonl'
        negative.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n'
                                    for row in rows))
        try:
            audit_pair(context, 'body_gap', negative, right)
        except ValueError as error:
            if 'comparison surface differs unexpectedly' not in str(error):
                raise
            negative_error = str(error)
        else:
            raise ValueError('Comparison accepted changed fixed surface')
    output = ROOT / 'body-geometry-draft' / 'primary-comparison-proof.json'
    output.write_text(json.dumps({'manifest_sha256': digest(manifest_path),
                                  'case_plan_sha256': digest(plan_path),
                                  'audit_sha256': digest(ROOT / 'comparison_audit.py'),
                                  'comparison_count': len(results),
                                  'comparisons': results,
                                  'negative_error': negative_error,
                                  'physical_acceptance_claimed': False}, indent=2) + '\n')
    print('primary comparisons passed', len(results), 'negative rejected')


if __name__ == '__main__':
    main()
