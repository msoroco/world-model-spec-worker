"""Exercise three exact access comparisons and changed-authority negative controls."""
import hashlib
import json
from pathlib import Path
from comparison_audit import FIXED_FIELDS,ComparisonError,audit
from package_spec import AID
HERE=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run():
 plan=json.loads((HERE/'case-plan.json').read_text());cases={x['case_id']:x for x in plan['cases']}
 if plan['assignment_id']!=AID or len(plan['comparisons'])!=3:raise ValueError('three exact comparisons required')
 reports=[]
 for comparison in plan['comparisons']:
  records=[]
  for case_id in comparison['case_ids']:
   case=cases[case_id]
   record={'format':'controlled-access-delivery-measurement','case_id':case_id,'native_result_sha256':hashlib.sha256(case_id.encode()).hexdigest(),'frame_count':900,'full_video_decode':True,'actual_pixels':True,'physical_completion':True,'observables':{'crossing at indicated versus unindicated entrance':case['requested_indicated'],'source-bound driver-view visibility of erected notice':case['requested_notice_visible'],'crossing at indicated versus unindicated exit':case['requested_indicated']},'diagnostic_fixture':True,'legal_verdict':None}
   record.update({key:'synthetic-fixed-'+key for key in FIXED_FIELDS});record['duration_frames']=900;records.append(record)
  positive=audit(records,deliberate_differences=comparison['deliberate_differences']);negative=json.loads(json.dumps(records));negative[1]['authority_determination_sha256']='changed-authority'
  try:audit(negative,deliberate_differences=comparison['deliberate_differences'])
  except ComparisonError as error:
   if 'fixed condition changed: authority_determination_sha256' not in str(error):raise
   negative_error=str(error)
  else:raise ValueError('changed authority accepted')
  log=HERE/('proof-comparison-'+comparison['comparison_id']+'.log');log.write_text('positive: '+positive['status']+'\nnegative: '+negative_error+'\nsynthetic CPU protocol; Native acceptance false\n')
  reports.append({'comparison_id':comparison['comparison_id'],'case_ids':comparison['case_ids'],'script':'comparison_audit.py','script_sha256':sha(HERE/'comparison_audit.py'),'diagnostic_fixture':True,'source_verified':False,'positive_exit_code':0,'negative_rejected':True,'log':log.name,'log_sha256':sha(log),'legal_verdict':None})
 (HERE/'comparison-proposal.json').write_text(json.dumps({'format':'controlled-access-exact-comparison-proposal','assignment_id':AID,'comparisons':reports,'legal_verdict':None},indent=2)+'\n');return len(reports)
if __name__=='__main__':print('controlled-access comparison CPU proofs:',run())
