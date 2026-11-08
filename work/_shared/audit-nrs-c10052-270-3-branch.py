"""Independently audit the C10052 exact source-topic branch mapping."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
LAW='NRS-484B-270-3'
ASSIGNMENT='training__C10052__NRS-484B-270-3__motor_vehicle_driver'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    source=json.loads((ROOT/'inputs/coverage/branch-sources.json').read_text())['laws'][LAW]
    matrix_path=ROOT/'work/_shared/branch-coverage.json'
    matrix=json.loads(matrix_path.read_text())['laws'][LAW]
    local=json.loads((ROOT/'work'/ASSIGNMENT/'statutory-branch-review.json').read_text())
    branches=matrix['branches']
    assert len(branches)==len(local['branches'])==12
    assert matrix['source_topic_count']==len(source['topics'])==9
    assert {b['branch_id'].split('__')[-1] for b in branches}=={b['id'] for b in local['branches']}
    assert all(b['assignment_id']==ASSIGNMENT for b in branches)
    statuses={b['branch_id'].split('__')[-1]:b['status'] for b in branches}
    assert statuses['prohibition_enter']=='runnable'
    assert statuses['prohibition_stop_stand']=='runnable'
    assert statuses['prohibition_drive']=='runnable'
    assert statuses['exception_a']=='runnable'
    assert all(status=='pending_review' for name,status in statuses.items()
               if name not in ('prohibition_enter','prohibition_stop_stand',
                               'prohibition_drive','exception_a'))
    mapping={b['branch_id'].split('__')[-1]:set(b['topic_ids']) for b in branches}
    assert mapping['prohibition_stop_stand']=={'text-1','reviewed-scope-0'}
    assert all(mapping[name]=={'text-1'} for name in
               ('prohibition_enter','prohibition_park','prohibition_drive'))
    assert mapping['yield_riders']==mapping['yield_qualifying_pedestrian']=={'text-0'}
    for i,letter in enumerate('abcdef',2):
        assert mapping['exception_'+letter]=={'text-'+str(i)}
    assert set().union(*mapping.values())==set(source['topics'])
    work=ROOT/'work'/ASSIGNMENT
    plan=json.loads((work/'case-plan.json').read_text())
    enter=next(b for b in branches if b['branch_id'].endswith('__prohibition_enter'))
    cases={c['case_id'] for c in plan['cases']}
    comparisons={c['comparison_id']:c for c in plan['comparisons']}
    expected_cases={ASSIGNMENT+'__probe_c_alley_entry',ASSIGNMENT+'__probe_d_no_entry'}
    expected_comparison=ASSIGNMENT+'__comparison_entry_no_entry'
    assert set(enter['case_ids'])==expected_cases<=cases
    assert enter['comparison_ids']==[expected_comparison]
    assert set(comparisons[expected_comparison]['case_ids'])==expected_cases
    for name,digest in enter['cpu_proofs'].items():
        assert sha(work/name)==digest,name
    for script in ('audit-alley-package-v1.py','audit-no-entry.py'):
        result=subprocess.run([sys.executable,str(work/script)],cwd=ROOT,
                              capture_output=True,text=True,timeout=120)
        assert result.returncode==0,(script,result.stdout,result.stderr)
        assert json.loads(result.stdout)['passed'] is True
    no_entry=json.loads((work/'no-entry-audit.json').read_text())
    assert no_entry['controlled_entry_frames']==119
    assert len(no_entry['package_receipts'])==4
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        summary=json.loads((work/('no-entry-package-'+candidate+'-summary.json')).read_text())
        assert summary['manifest_sha256']==sha(work/'draft-no-entry-execution-manifest.json')
        assert summary['positive_receipt_sha256']
        assert summary['negative_exit_code']!=0 and summary['trigger_negative_exit_code']!=0
    drive=next(b for b in branches if b['branch_id'].endswith('__prohibition_drive'))
    assert set(drive['case_ids'])=={ASSIGNMENT+'__probe_a',ASSIGNMENT+'__probe_b'}
    assert drive['comparison_ids']==[ASSIGNMENT+'__comparison']
    assert all(sha(work/name)==digest for name,digest in drive['cpu_proofs'].items())
    drive_run=subprocess.run([sys.executable,str(work/'audit-drive-within-cpu.py')],
                             cwd=ROOT,capture_output=True,text=True,timeout=120)
    assert drive_run.returncode==0,(drive_run.stdout,drive_run.stderr)
    drive_proof=json.loads(drive_run.stdout)
    assert drive_proof['passed'] is True and len(drive_proof['candidate_pairs'])==4
    assert all(row['reference']['moving_occupied_frames']==0 and
               row['contrast']['moving_occupied_frames']==71 and
               row['speed_magnitude_different_frames']==40
               for row in drive_proof['candidate_pairs'])
    exception=next(b for b in branches if b['branch_id'].endswith('__exception_a'))
    assert set(exception['case_ids'])==expected_cases
    assert exception['comparison_ids']==[expected_comparison]
    assert all(sha(work/name)==digest for name,digest in exception['cpu_proofs'].items())
    exception_run=subprocess.run([sys.executable,str(work/'audit-exception-a-cpu.py')],
                                 cwd=ROOT,capture_output=True,text=True,timeout=120)
    assert exception_run.returncode==0,(exception_run.stdout,exception_run.stderr)
    exception_proof=json.loads(exception_run.stdout)
    assert exception_proof['passed'] is True and len(exception_proof['exact_candidate_pairs'])==4
    assert exception_proof['legal_exception_observed'] is False
    assert all(row['alley']['time_bounded_geometry_candidate'] and
               row['no_entry']['moving_facility_occupied_frames']==0 and
               row['longitudinal_trace_identical'] is False
               for row in exception_proof['exact_candidate_pairs'])
    assert exception_proof['controlled_near']['simultaneous_moving_overlap_frames']==27
    assert exception_proof['controlled_away']['simultaneous_moving_overlap_frames']==0
    shared=json.loads((ROOT/'work/_shared/branch-review.json').read_text())
    assert shared['coverage_sha256']==sha(matrix_path)
    assert LAW in shared['missing_branches']
    return {'passed':True,'law_id':LAW,'topics':9,'pending_branches':8,
            'runnable_branches':4,'coverage_sha256':sha(matrix_path)}


if __name__=='__main__':
    print(json.dumps(audit(),indent=2))
