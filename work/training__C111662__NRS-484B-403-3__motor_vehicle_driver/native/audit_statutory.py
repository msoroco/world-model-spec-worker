"""Exact-source statutory coverage ledger for the U-turn location pair."""
import json
from build import CASE, HERE, PLAN, SOURCE, SOURCE_SHA, sha, put


def audit():
    source=json.loads(SOURCE.read_text());plan=json.loads(PLAN.read_text())
    law=source['law_record']['text']
    clauses={
        'vehicle_u_turn':'The driver of a vehicle shall not make a U-turn',
        'business_district':'in a business district',
        'intersection_exception':'except at an intersection',
        'divided_highway_opening_exception':'or on a divided highway where an appropriate opening or crossing place exists',
    }
    if sha(SOURCE)!=SOURCE_SHA or plan['source_law_text']!=law or \
            any(fragment not in law for fragment in clauses.values()):
        raise ValueError('Exact statutory source or clause changed')
    cases={row['case_id'] for row in plan['cases']}
    if cases!={CASE.name+'__reference',CASE.name+'__contrast'} or \
            not any(row.get('status')=='exception_pending' and not row.get('case_ids')
                    for row in plan['requirement_dispositions']):
        raise ValueError('Statutory case or pending exception disposition changed')
    ledger=[]
    for name,fragment in clauses.items():
        has_request=name!='divided_highway_opening_exception'
        ledger.append({'clause':name,'exact_text':fragment,
                       'authored_request_or_synthetic_measurement':has_request,
                       'original_physical_proof':False,'legal_applicability_proven':False,
                       'case_ids':sorted(cases) if has_request else []})
    result={'format':'c111662-4033-statutory-coverage-v1','assignment_id':CASE.name,
            'assignment_sha256':SOURCE_SHA,'clauses':ledger,'source_clause_count':len(ledger),
            'original_native_observed':False,'delivery_ready':False}
    put(HERE/'statutory-coverage.json',result)
    return result


if __name__=='__main__':print(json.dumps({'source_clause_count':audit()['source_clause_count'],
                                          'original_native_observed':False}))
