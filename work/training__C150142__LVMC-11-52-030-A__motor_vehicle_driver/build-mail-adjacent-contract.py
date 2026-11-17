"""Bind the two frozen mail clauses to executed source-backed measurements."""
import hashlib
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--slug', choices=('mail_adjacent_deposit',
                                            'mail_no_box_deposit'),
                        default='mail_adjacent_deposit')
    args = parser.parse_args()
    slug = args.slug
    case_id = ROOT.name + '__' + slug
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    rows = plan['requirement_dispositions']
    if ([rows[i]['requirement'] for i in (7, 8)] != ['text-7', 'text-8'] or
            any(case_id not in rows[i]['case_ids'] for i in (7, 8))):
        raise ValueError('Frozen mail clause selection changed')
    common = {'source': 'inputs/coverage/branch-sources.json'}
    contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
                'requirements': [
                    dict(common, disposition_index=7, requirement='text-7',
                         output_key='signed_curb_observation',
                         method='signed_context', value_type='object',
                         kind='measured', inputs=[
                             'native-raw-actors.jsonl', 'native-map-readback.json',
                             'native-mail-worker-actors.jsonl',
                             'native-mail-parcel-inventory.jsonl']),
                    dict(common, disposition_index=8, requirement='text-8',
                         output_key='mail_exception_source_text',
                         method='mail_clause_context', value_type='text',
                         kind='sourced_context', inputs=['statutory-context.json'])],
                'negative': {'remove': ['native-mail-parcel-inventory.jsonl'],
                             'error_contains': 'Missing required source: native-mail-parcel-inventory.jsonl'},
                'scope': 'Observed mail worker and parcel source context plus exact mail clause; no legal verdict or physical acceptance'}
    output = ROOT / 'selected-measurement-contracts' / (slug + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + '\n')
    canonical = json.loads((ROOT / 'execution-manifest.json').read_text())
    entry = next(e for e in canonical['cases'] if e['case_id'] == case_id)
    entry['measurement_contract'] = output.relative_to(ROOT).as_posix()
    entry['fixture_recipe'] = ('work/' + ROOT.name + '/selected-diagnostics/' +
                               slug + '/primary-recipe.json')
    pilot = ROOT / ('execution-manifest-mail-adjacent-pilot.json'
                    if slug == 'mail_adjacent_deposit'
                    else 'execution-manifest-mail-no-box-pilot.json')
    canonical['status'] = ('selected_mail_adjacent_cpu_pilot'
                           if slug == 'mail_adjacent_deposit'
                           else 'selected_mail_no_box_cpu_pilot')
    canonical['delivery_ready'] = False
    pilot.write_text(json.dumps(canonical, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'case_id': case_id, 'contract_sha256': sha(output),
                      'pilot_manifest_sha256': sha(pilot),
                      'delivery_ready': False}))


if __name__ == '__main__':
    main()
