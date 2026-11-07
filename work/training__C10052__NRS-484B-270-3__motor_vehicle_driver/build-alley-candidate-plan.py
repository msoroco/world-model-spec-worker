"""Bind the unselected exception-A case to four distinct Native turn proposals."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from alley_engineering import parameters,TRIGGERS


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    names=('primary','fallback1','fallback2','fallback3')
    source_names=('alley_geometry.py','alley_engineering.py','measure_alley_transition.py',
                  'measure_alley_triggers.py','alley_runner.py','alley-native-config.json')
    sources={name:sha(HERE/'native'/name) for name in source_names}
    trigger_summary=sha(HERE/'alley-trigger-summary.json')
    crossing_summary=sha(HERE/'alley-transition-summary.json')
    offline=json.loads((HERE/'draft-alley-offline-summary.json').read_text())
    assert len(offline['results'])==4
    offline_rows={row['candidate_id']:row for row in offline['results']}
    assert set(offline_rows)==set(names)
    assert all(row['exit_code']==0 for row in offline_rows.values())
    manifest=json.loads((HERE/'draft-alley-execution-manifest.json').read_text())
    entry=manifest['cases'][0]
    candidates=[]
    for name in names:
        selected=entry if name=='primary' else next(c for c in entry['candidates'] if c['id']==name)
        assert selected['construction_sha256']==offline_rows[name]['construction_sha256']
        package_path=HERE/('alley-package-'+name+'-summary.json')
        package=json.loads(package_path.read_text())
        assert package['candidate_id']==name and package['construction_sha256']==selected['construction_sha256']
        assert package['negative_exit_code']!=0 and package['selected'] is False and package['accepted'] is False
        candidate={'id':name,'native_parameters':parameters(name),
            'route_source':'native/alley_geometry.py',
            'source_sha256':sources,'status':'unselected_exact_cpu_diagnostic_proven',
            'construction_sha256':selected['construction_sha256'],
            'offline_command_log_sha256':offline_rows[name]['command_log_sha256'],
            'portable_v1_summary_sha256':sha(package_path)}
        if name!='primary':
            candidate['measured_trigger']=TRIGGERS[name]
            candidate['synthetic_trigger_proof_sha256']=trigger_summary
        candidates.append(candidate)
    plan={'format':'c10052-exception-a-candidate-plan-v1',
        'case_id':HERE.name+'__probe_c_alley_entry',
        'assignment_id':HERE.name,'cell_id':'C10052',
        'law_id':'NRS-484B-270-3','actor':'motor_vehicle_driver',
        'statutory_branch':'exception_a_entering_or_exiting_alley_or_driveway',
        'controlled_comparison':'near alley turn versus matched away-from-alley crossing',
        'synthetic_crossing_proof_sha256':crossing_summary,
        'candidates':candidates,'selected':False,'ready':False,
        'native_execution_proven':False,'exact_offline_proven':True,
        'portable_v1_diagnostic_proven':True,
        'portable_compatibility_proven':False,
        'offline_summary_sha256':sha(HERE/'draft-alley-offline-summary.json'),
        'manifest_sha256':sha(HERE/'draft-alley-execution-manifest.json'),
        'physical_success_claimed':False}
    (HERE/'alley-candidate-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print(json.dumps({'case_id':plan['case_id'],'candidates':len(candidates),
        'selected':False,'source_sha256':sources},sort_keys=True))


if __name__=='__main__':main()
