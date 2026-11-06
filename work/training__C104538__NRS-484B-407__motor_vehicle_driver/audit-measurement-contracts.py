"""Independently bind draft obligations to all current selected-required rows."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    plan=json.loads((HERE/'case-plan.json').read_text())
    summary=json.loads((HERE/'draft-measurement-contract-summary.json').read_text())
    assert summary['count']==3 and summary['pinned_contracts_passed']==0
    assert {r['case_id'] for r in summary['cases']}=={c['case_id'] for c in plan['cases']}
    for entry in summary['cases']:
        path=HERE/entry['contract'];contract=json.loads(path.read_text())
        assert sha(path)==entry['sha256']
        assert contract['case_id']==entry['case_id']
        assert contract['status']=='requires_original_native_sources'
        assert contract['pinned_contract_validated'] is False
        assert contract['saved_native_report_verified'] is False
        assert len(contract['requirements'])==len(plan['requirement_dispositions'])==4
        suffix=entry['case_id'].split('__')[-1]
        for name,digest in contract['authored_source_hashes'].items():
            assert digest==sha(HERE/'draft-sightline'/suffix/name)
        for index,row in enumerate(contract['requirements']):
            disposition=plan['requirement_dispositions'][index]
            assert row['disposition_index']==index
            assert row['requirement']==disposition['requirement']
            assert row['source']==disposition['source']
            assert entry['case_id'] in disposition['case_ids']
            assert row['required_original_native_inputs'] and row['measurement_obligation']
            assert row['native_value_measured'] is False
    return {'passed':True,'draft_contracts':3,'requirements_per_case':4,
            'pinned_contracts_passed':0,'native_measurements':0}


if __name__=='__main__':print(json.dumps(audit(),indent=2))
