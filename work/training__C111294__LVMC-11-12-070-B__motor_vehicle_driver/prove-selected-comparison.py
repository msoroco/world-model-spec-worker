"""Bind the fixed-condition comparison to the selected exact-case handoff."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_auditor():
    path = HERE / 'audit-priority-comparison.py'
    spec = importlib.util.spec_from_file_location('priority_comparison', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    expected = [HERE.name + '__probe_1', HERE.name + '__probe_2']
    entries = manifest['cases']
    if [entry['case_id'] for entry in entries] != expected or any(entry['kind'] != 'delivery' for entry in entries):
        raise ValueError('Selected exact comparison identities differ')
    comparison = plan['comparisons'][0]
    if comparison['case_ids'] != expected:
        raise ValueError('Selected comparison does not match case plan')
    for entry in entries:
        source = HERE / entry['construction']
        if sha(source) != entry['construction_sha256']:
            raise ValueError('Selected construction changed')
        proof = HERE / entry['compatibility']['receipt']
        if sha(proof) != entry['compatibility']['sha256']:
            raise ValueError('Selected compatibility changed')
        receipt = json.loads(proof.read_text())
        if receipt['case_id'] != entry['case_id'] or receipt['construction_sha256'] != entry['construction_sha256']:
            raise ValueError('Selected compatibility refers to another construction')
    auditor = load_auditor()
    first = auditor.load_source(HERE / 'current-v2-probe-1-fixture', expected[0])
    second = auditor.load_source(HERE / 'current-v2-probe-2-fixture', expected[1])
    result = auditor.audit(first, second)
    negatives = []
    wrong = dict(second)
    wrong['road_sha256'] = '0' * 64
    changed_entrant = dict(second)
    changed_entrant['samples'] = [dict(row) for row in second['samples']]
    changed_entrant['samples'][200] = dict(changed_entrant['samples'][200])
    changed_entrant['samples'][200]['entrant'] = {'x_m': -999}
    for label, damaged in [('changed_road', wrong), ('changed_entrant', changed_entrant)]:
        try:
            auditor.audit(first, damaged)
        except (ValueError, IndexError) as exc:
            negatives.append({'mutation': label, 'error': str(exc)})
        else:
            raise AssertionError('Changed selected comparison source passed: ' + label)
    output = {'format': 'c111294-selected-comparison-cpu-proof-v1',
              'passed': True, 'comparison_id': comparison['comparison_id'],
              'case_ids': expected, 'manifest_sha256': sha(HERE / 'execution-manifest.json'),
              'auditor_sha256': sha(HERE / 'audit-priority-comparison.py'),
              'primary_construction_sha256': entries[0]['construction_sha256'],
              'contrast_construction_sha256': entries[1]['construction_sha256'],
              'comparison': result, 'negative_rejections': negatives,
              'original_native_observed': False, 'legal_acceptance_claimed': False}
    path = HERE / 'selected-comparison-audit.json'
    path.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'passed': True, 'negative_rejections': len(negatives),
                      'receipt_sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()
