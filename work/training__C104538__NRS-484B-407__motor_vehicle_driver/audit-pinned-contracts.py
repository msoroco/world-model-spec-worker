"""Independent C104538 exact-case contract and synthetic receipt audit."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
SHA=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    plan=json.loads((ROOT/'case-plan.json').read_text())
    contracts=json.loads((ROOT/'pinned-contract-summary.json').read_text())
    saved=json.loads((ROOT/'pinned-contract-saved-summary.json').read_text())
    assert contracts['pinned_validator_pass_count']==3
    assert saved['positive_saved_value_count']==3 and saved['negative_missing_body_count']==3
    assert saved['original_native_measurement_count']==saved['selected_case_count']==0
    expected={case['case_id'] for case in plan['cases']}
    assert {row['case_id'] for row in contracts['cases']}==expected
    assert {row['case_id'] for row in saved['cases']}==expected
    for row in saved['cases']:
        suffix=row['case_suffix'];case_id=row['case_id']
        contract_row=next(item for item in contracts['cases'] if item['case_id']==case_id)
        assert SHA(ROOT/contract_row['contract'])==contract_row['contract_sha256']==row['contract_sha256']
        contract=json.loads((ROOT/contract_row['contract']).read_text())
        assert contract['case_id']==case_id
        assert len(contract['requirements'])==4
        assert {item['disposition_index'] for item in contract['requirements']}=={0,1,2,3}
        for item in contract['requirements']:
            original=plan['requirement_dispositions'][item['disposition_index']]
            assert item['requirement']==original['requirement'] and item['source']==original['source']
            assert item['method']=='measure_case_sources' and item['kind']=='measured'
        fixture=REPO/'.runtime-work/c104538/pinned-contract-probes-v1'/suffix
        positive=fixture/'positive';negative=fixture/'negative_missing_body'
        assert SHA(positive/'result.json')==row['positive_result_sha256']
        assert SHA(positive/'analysis-report.json')==row['positive_report_sha256']
        result=json.loads((positive/'result.json').read_text())
        report=json.loads((positive/'analysis-report.json').read_text())
        assert result['case_id']==report['case_id']==case_id
        assert result['provenance_kind']=='synthetic'
        assert all(result[key] is False for key in ('setup_confirmed','accepted','legal_verdict_claimed'))
        assert result['target_checks'][0]['matched'] is False
        assert set(report['measurements'])=={item['output_key'] for item in contract['requirements']}
        for item in contract['requirements']:
            evidence=report['measurements'][item['output_key']]
            assert set(evidence['sources'])==set(item['inputs'])
            assert all(SHA(positive/name)==digest for name,digest in evidence['sources'].items())
        assert not (negative/'native_body_history.jsonl').exists()
        assert [receipt['label'] for receipt in row['receipts']]==['positive','negative_missing_body']
        for receipt in row['receipts']:
            assert SHA(ROOT/receipt['log'])==receipt['log_sha256']
            if receipt['label']=='positive':assert receipt['exit_code']==0
            else:
                assert receipt['exit_code']!=0
                assert contract['negative']['error_contains'] in (ROOT/receipt['log']).read_text()
    return {'contract_cases':3,'synthetic_saved_positives':3,
            'missing_body_negatives':3,'native_physical_claims':0}


if __name__=='__main__':print(json.dumps(audit()))
