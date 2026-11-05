"""Independent hash and candidate-invariant audit of unselected CPU drafts."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
FOLDER=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.candidate_constructions import validate
from worker_exchange.measurement_contract import validate as validate_measurement


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=json.loads((FOLDER/'draft-execution-manifest.json').read_text())
    summary=json.loads((FOLDER/'draft-offline-summary.json').read_text())
    assert manifest['status']=='draft_not_selected'
    assert len(manifest['cases'])==5 and len(summary['results'])==20
    expected=set()
    for entry in manifest['cases']:
        validate(FOLDER,entry,'NRS-484B-223-3b','C394300',
                 required=False,require_alternate=True,candidate_count=4)
        contract=json.loads((FOLDER/entry['measurement_contract']).read_text())
        plan=json.loads((FOLDER/'case-plan.json').read_text())
        source=json.loads((FOLDER/entry['construction']).read_text())
        analysis=next(f['content'] for f in source['files'] if f['path']=='finalize.py')
        validate_measurement(contract,plan['requirement_dispositions'],analysis,entry['case_id'])
        for item in source['files']:
            if item['path']=='config.json':continue
            native=FOLDER/'native'/Path(item['path']).name
            assert native.read_text()==item['content'],native
        expected.update((entry['case_id'],name) for name in
                        ('primary','fallback1','fallback2','fallback3'))
    actual=set()
    for receipt in summary['results']:
        key=receipt['case_id'],receipt['candidate_id']
        assert key not in actual
        actual.add(key)
        entry=next(e for e in manifest['cases'] if e['case_id']==key[0])
        source=entry if key[1]=='primary' else next(c for c in entry['candidates'] if c['id']==key[1])
        assert receipt['construction_sha256']==source['construction_sha256']
        assert digest(FOLDER/source['construction'])==source['construction_sha256']
        assert receipt['exit_code']==0
        assert digest(FOLDER/receipt['command_log'])==receipt['command_log_sha256']
        assert digest(FOLDER/receipt['unit_log'])==receipt['unit_log_sha256']
        unit=(FOLDER/receipt['unit_log']).read_text()
        assert 'Ran 14 tests' in unit and '\nOK\n' in unit
        assert 'offline_geometry' in unit and '"native_center_lane_design_verified": false' in unit
    assert actual==expected
    print(json.dumps({'passed':True,'cases':5,'draft_candidates':20,
                      'offline_unit_tests_per_bundle':14,
                      'selected_delivery_cases':0,'physical_verified':False}))


if __name__=='__main__':main()
