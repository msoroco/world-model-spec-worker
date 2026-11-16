"""Verify selected signal-distance CPU receipts and saved source measurements."""
import hashlib,json
from pathlib import Path
F=Path(__file__).resolve().parent;R=F.parent.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 m=json.loads((F/'execution-manifest.json').read_text());entries=[e for e in m['cases'] if e['case_id'].endswith(('__signal_advance_100_below_25','__signal_advance_100_above_36'))]
 assert len(m['cases'])==16 and len(entries)==2
 proofs=[]
 for e in entries:
  label='below' if e['signal_target_m']==25 else 'above'
  for item in [e,*e['candidates']]:
   ident=item.get('id','primary');o=item['offline'];c=item['compatibility'];p=item['post_capture'];rec=json.loads((F/c['receipt']).read_text())
   assert sha(F/item['construction'])==item['construction_sha256']==o['construction_sha256']==rec['construction_sha256']
   assert sha(F/o['log'])==o['log_sha256'] and o['exit_code']==0 and json.loads((F/o['log']).read_text())['offline_passed'] is True
   assert sha(F/c['receipt'])==c['sha256'] and rec['passed'] is True and rec['candidate_id']==ident
   assert rec['negative_removed']=='interaction_history.jsonl' and b'Missing required source: interaction_history.jsonl' in (F/c['negative_log']).read_bytes()
   assert sha(F/p['test_log'])==p['test_log_sha256'] and p['test_exit_code']==0 and p['recorded_only'] is True
   output=R/f'.runtime-work/c109749-canonical-{label}-{ident}-compat-v1';a=json.loads((output/'analysis-report.json').read_text());v=a['measurements']['signal_advance_observation']['value'];distance=v['observed_continuous_approach_distance_m']
   assert abs(distance-e['signal_target_m'])<.05 and v['probes']['30.48']['observable_distance_met']==(distance>=30.48) and v['legal_verdict_asserted'] is False
   saved=R/f'.runtime-work/c109749-canonical-{label}-{ident}-saved-v1/v0001/processing.json';s=json.loads(saved.read_text());assert s['recorded_only'] is True and s['originals_preserved'] is True and s['physical_acceptance_claimed'] is False and s['legal_acceptance_claimed'] is False
   proofs.append({'case_id':e['case_id'],'candidate_id':ident,'observed_distance_m':distance,'construction_sha256':item['construction_sha256'],'saved_sha256':sha(saved)})
 print(json.dumps({'format':'c109749-canonical-signal-distance-proof','selected_cases':len(m['cases']),'paths':proofs,'native_or_legal_acceptance_claimed':False},indent=2))
if __name__=='__main__':main()
