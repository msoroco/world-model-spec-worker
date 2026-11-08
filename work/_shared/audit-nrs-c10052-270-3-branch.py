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
    assert statuses['prohibition_park']=='runnable'
    assert statuses['exception_a']=='runnable'
    assert all(status=='pending_review' for name,status in statuses.items()
               if name not in ('prohibition_enter','prohibition_stop_stand',
                               'prohibition_drive','prohibition_park','exception_a'))
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
    park=next(b for b in branches if b['branch_id'].endswith('__prohibition_park'))
    park_cases={ASSIGNMENT+'__probe_park_released',ASSIGNMENT+'__probe_park_held'}
    assert set(park['case_ids'])==park_cases<=cases
    park_comparison=ASSIGNMENT+'__comparison_park_act'
    assert park['comparison_ids']==[park_comparison]
    assert set(comparisons[park_comparison]['case_ids'])==park_cases
    assert all(sha(work/name)==digest for name,digest in park['cpu_proofs'].items())
    park_run=subprocess.run([sys.executable,str(work/'audit-park-distinct-packages.py')],
                            cwd=ROOT,capture_output=True,text=True,timeout=120)
    assert park_run.returncode==0,(park_run.stdout,park_run.stderr)
    park_proof=json.loads(park_run.stdout)
    assert park_proof['passed'] is True and len(park_proof['candidate_pairs'])==4
    assert park_proof['legal_park_observed'] is False
    rider=next(b for b in branches if b['branch_id'].endswith('__yield_riders'))
    rider_types=('bicycle','electric_bicycle','electric_scooter')
    expected_rider_cases={ASSIGNMENT+'__rider_'+kind+'_'+response
                          for kind in rider_types for response in ('clear','conflict')}
    assert rider['status']=='pending_review'
    assert set(rider['case_ids'])==expected_rider_cases<=cases
    assert set(rider['comparison_ids'])=={
        ASSIGNMENT+'__comparison_rider_'+kind for kind in rider_types}
    for kind in rider_types:
        cid=ASSIGNMENT+'__comparison_rider_'+kind
        assert set(comparisons[cid]['case_ids'])=={
            ASSIGNMENT+'__rider_'+kind+'_'+response for response in ('clear','conflict')}
    assert all(sha(work/name)==digest for name,digest in rider['cpu_proofs'].items())
    exact_rider_run=subprocess.run([sys.executable,str(work/'audit-rider-case-candidates.py')],
                                   cwd=ROOT,capture_output=True,text=True,timeout=120)
    assert exact_rider_run.returncode==0,(exact_rider_run.stdout,exact_rider_run.stderr)
    exact_rider_proof=json.loads(exact_rider_run.stdout)
    assert exact_rider_proof['passed'] and exact_rider_proof['candidates']==24
    assert exact_rider_proof['original_native_capture_executed'] is False
    rider_run=subprocess.run([sys.executable,str(work/'audit-rider-yield-timing.py')],
                             cwd=ROOT,capture_output=True,text=True,timeout=120)
    assert rider_run.returncode==0,(rider_run.stdout,rider_run.stderr)
    rider_proof=json.loads(rider_run.stdout)
    assert rider_proof['passed'] and rider_proof['controlled_pairs']==3
    assert rider_proof['legal_yield_observed'] is False
    trigger_run=subprocess.run([sys.executable,str(work/'audit-rider-fallback-triggers.py')],
                               cwd=ROOT,capture_output=True,text=True,timeout=120)
    assert trigger_run.returncode==0,(trigger_run.stdout,trigger_run.stderr)
    trigger_proof=json.loads(trigger_run.stdout)
    assert trigger_proof['passed'] and trigger_proof['rows']==24
    assert trigger_proof['isolated_crossings']==18
    assert trigger_proof['original_camera_pixels_verified'] is False
    candidate_run=subprocess.run([sys.executable,str(work/'native/rider_candidates.py')],
                                 cwd=ROOT,capture_output=True,text=True,timeout=120)
    assert candidate_run.returncode==0,(candidate_run.stdout,candidate_run.stderr)
    candidate_proof=json.loads(candidate_run.stdout)
    assert candidate_proof['cases']==6 and candidate_proof['candidates_per_case']==4
    assert candidate_proof['original_native_actor_verified'] is False
    shared=json.loads((ROOT/'work/_shared/branch-review.json').read_text())
    assert shared['coverage_sha256']==sha(matrix_path)
    assert LAW in shared['missing_branches']
    return {'passed':True,'law_id':LAW,'topics':9,'pending_branches':7,
            'runnable_branches':5,'coverage_sha256':sha(matrix_path)}


if __name__=='__main__':
    print(json.dumps(audit(),indent=2))
