"""Independent source and law-preservation audit of four alley construction seeds."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    plan=json.loads((HERE/'alley-candidate-plan.json').read_text())
    assert plan['assignment_id']==HERE.name
    assert plan['case_id']==HERE.name+'__probe_c_alley_entry'
    assert plan['cell_id']=='C10052' and plan['law_id']=='NRS-484B-270-3'
    assert plan['actor']=='motor_vehicle_driver'
    assert plan['statutory_branch']=='exception_a_entering_or_exiting_alley_or_driveway'
    assert plan['selected'] is False and plan['ready'] is False
    assert plan['exact_offline_proven'] is True and plan['portable_v1_diagnostic_proven'] is True
    assert plan['portable_compatibility_proven'] is False and plan['native_execution_proven'] is False
    assert plan['offline_summary_sha256']==sha(HERE/'draft-alley-offline-summary.json')
    assert plan['manifest_sha256']==sha(HERE/'draft-alley-execution-manifest.json')
    manifest=json.loads((HERE/'draft-alley-execution-manifest.json').read_text())
    offline=json.loads((HERE/'draft-alley-offline-summary.json').read_text())
    entry=manifest['cases'][0]
    assert plan['synthetic_crossing_proof_sha256']==sha(HERE/'alley-transition-summary.json')
    candidates=plan['candidates']
    assert [row['id'] for row in candidates]==['primary','fallback1','fallback2','fallback3']
    base=candidates[0]['native_parameters']
    expected={'fallback1':('approach_start_x_m',-55.0),
              'fallback2':('turn_speed_mps',1.8),
              'fallback3':('camera_profile','wide_alley_view')}
    for row in candidates:
        assert row['status']=='unselected_exact_cpu_diagnostic_proven'
        assert row['route_source']=='native/alley_geometry.py'
        assert all(sha(HERE/'native'/name)==digest for name,digest in row['source_sha256'].items())
        selected=entry if row['id']=='primary' else next(c for c in entry['candidates'] if c['id']==row['id'])
        offline_row=next(r for r in offline['results'] if r['candidate_id']==row['id'])
        package_path=HERE/('alley-package-'+row['id']+'-summary.json')
        package=json.loads(package_path.read_text())
        assert row['construction_sha256']==selected['construction_sha256']==offline_row['construction_sha256']
        assert sha(HERE/selected['construction'])==row['construction_sha256']
        assert row['offline_command_log_sha256']==offline_row['command_log_sha256']
        assert sha(HERE/offline_row['command_log'])==row['offline_command_log_sha256']
        assert row['portable_v1_summary_sha256']==sha(package_path)
        assert package['positive_receipt_sha256'] and package['negative_exit_code']!=0
        assert row['native_parameters']['turn_radius_m']==5.0
        if row['id']=='primary':
            assert row['native_parameters']=={'approach_start_x_m':-45.0,
                'turn_speed_mps':2.5,'turn_radius_m':5.0,'camera_profile':'standard'}
        else:
            key,value=expected[row['id']]
            assert {k:v for k,v in row['native_parameters'].items() if v!=base[k]}=={key:value}
            assert row['synthetic_trigger_proof_sha256']==sha(HERE/'alley-trigger-summary.json')
            assert row['measured_trigger']['source'] and row['measured_trigger']['metric']
            assert row['measured_trigger']['failure_condition']
    return {'passed':True,'case_id':plan['case_id'],'candidates':4,
            'distinct_changed_knobs':list(expected),
            'plan_sha256':sha(HERE/'alley-candidate-plan.json'),
            'selected':False,'ready':False}


if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
