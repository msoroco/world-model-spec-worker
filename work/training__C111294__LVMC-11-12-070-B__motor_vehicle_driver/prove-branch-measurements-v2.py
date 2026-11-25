"""Validate draft three-disposition outputs against exact selected fixture sources."""
import hashlib
import importlib.util
import json
from pathlib import Path

from scenario_pipeline.worker_exchange.measurement_contract import validate, verify_report

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejected(call):
    try:
        call()
    except ValueError:
        return True
    raise AssertionError('Missing measurement or source accepted')


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    source = HERE / 'branch-measurements-v2.py'
    spec = importlib.util.spec_from_file_location('branch_measurements_v2', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    entries = []
    for number in (1, 2):
        case = HERE.name + f'__probe_{number}'
        contract_path = HERE / f'branch-measurements-v2-probe-{number}.json'
        old = json.loads((HERE / f'current-v2-probe-{number}-measurement-contract.json').read_text())
        contract = dict(old)
        contract['requirements'] = list(old['requirements'])
        for index, key, method in (
                (1, 'prior_yield_antecedent', 'measure_prior_yield_antecedent'),
                (2, 'entrant_entry_phase', 'measure_entrant_entry_phase')):
            contract['requirements'].append({
                'disposition_index': index, 'requirement': plan['requirement_dispositions'][index]['requirement'],
                'source': plan['requirement_dispositions'][index]['source'],
                'output_key': key, 'method': method, 'value_type': 'object',
                'kind': 'measured', 'inputs': ['native_samples.jsonl', 'road.xodr']})
        validate(contract, plan['requirement_dispositions'], source.read_text(), case)
        fixture = HERE / f'current-v2-probe-{number}-fixture'
        public = json.loads((HERE / f'current-v2-probe-{number}-compatibility.json').read_text())
        observed = public['measurement_examples']['priority_requirement']['value']
        rows = [json.loads(line) for line in (fixture / 'native_samples.jsonl').read_text().splitlines()]
        report = {'measurements': {
            'priority_requirement': public['measurement_examples']['priority_requirement'],
            'prior_yield_antecedent': module.measure_prior_yield_antecedent(observed),
            'entrant_entry_phase': module.measure_entrant_entry_phase(observed, rows)}}
        measured = verify_report(contract, report, fixture)
        missing = {'measurements': {k: v for k, v in measured.items() if k != 'entrant_entry_phase'}}
        if not rejected(lambda: verify_report(contract, missing, fixture)):
            raise AssertionError('Missing entrant phase accepted')
        changed = {'measurements': dict(measured)}
        changed['measurements']['prior_yield_antecedent'] = {
            **changed['measurements']['prior_yield_antecedent'],
            'sources': {'native_samples.jsonl': '0' * 64, 'road.xodr': sha(fixture / 'road.xodr')}}
        if not rejected(lambda: verify_report(contract, changed, fixture)):
            raise AssertionError('Changed source accepted')
        no_crossing = [dict(row) for row in rows]
        no_crossing[200] = dict(no_crossing[200])
        no_crossing[200]['entrant'] = {**no_crossing[200]['entrant'], 'x_m': -12.0}
        if not rejected(lambda: module.measure_entrant_entry_phase(observed, no_crossing)):
            raise AssertionError('Broken crossing accepted')
        contract_path.write_text(json.dumps(contract, indent=2) + '\n')
        entries.append({'case_id': case, 'contract': contract_path.name,
                        'contract_sha256': sha(contract_path),
                        'source_sha256': sha(fixture / 'native_samples.jsonl'),
                        'new_output_keys': ['prior_yield_antecedent', 'entrant_entry_phase'],
                        'negative_rejections': ['missing_output', 'changed_source_hash', 'broken_crossing'],
                        'original_native_observed': False})
    receipt = {'format': 'c111294-branch-measurement-draft-v2', 'passed': True,
               'analysis_source': source.name, 'analysis_sha256': sha(source),
               'case_plan_sha256': sha(HERE / 'case-plan.json'),
               'cases': entries, 'selected_manifest_modified': False,
               'public_receipts_modified': False, 'ready': False}
    out = HERE / 'branch-measurements-v2-proof.json'
    out.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'cases': len(entries), 'proof_sha256': sha(out)}))


if __name__ == '__main__':
    main()
