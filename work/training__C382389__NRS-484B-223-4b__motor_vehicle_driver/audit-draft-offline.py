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
    assert len(manifest['cases'])==2 and len(summary['results'])==8
    expected=set()
    for entry in manifest['cases']:
        validate(FOLDER,entry,'NRS-484B-223-4b','C382389',
                 required=False,require_alternate=True,candidate_count=4)
        contract=json.loads((FOLDER/entry['measurement_contract']).read_text())
        plan=json.loads((FOLDER/'case-plan.json').read_text())
        source=json.loads((FOLDER/entry['construction']).read_text())
        embedded={item['path']:item['content'] for item in source['files']}
        assert 'fallback_triggers.py' in embedded and 'tests/test_fallback_triggers.py' in embedded
        assert all(name in embedded['fallback_triggers.py'] for name in
                   ('connected_requested_lane_link','maximum_connector_entry_route_error_m',
                    'approach_pixel_visible_fraction','road_geometry_sha256','video_sha256'))
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
        assert 'Ran 11 tests' in unit and '\nOK\n' in unit
        assert 'offline_geometry' in unit and '"right_turn_lane_design_and_signage_native_verified": false' in unit
    assert actual==expected
    print(json.dumps({'passed':True,'cases':2,'draft_candidates':8,
                      'offline_unit_tests_per_bundle':11,
                      'selected_delivery_cases':0,'physical_verified':False}))


if __name__=='__main__':main()
