"""Bind rerun independent delivery mechanics and controlled pair audit."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p=HERE/'execution-manifest.json';m=json.loads(p.read_text())
for e in m['cases']:
 suffix=e['case_id'].removeprefix(HERE.name+'__')
 positive=HERE/f'update602-delivery-{suffix}-positive.log';negative=HERE/f'update602-delivery-{suffix}-negative.log'
 assert positive.is_file() and negative.is_file()
 assert 'cpu_audit_mechanics_passed' in positive.read_text()
 assert 'Original actor/frame/trace join differs at 0' in negative.read_text()
 a=e['delivery_acceptance'];a['test_log']=positive.name;a['test_log_sha256']=sha(positive);a['negative_log']=negative.name;a['negative_log_sha256']=sha(negative)
 audit=HERE/'update602-pair-audit.json';log=HERE/'update602-audit-pairs.log'
 assert json.loads(audit.read_text())['passed'] and json.loads(audit.read_text())['pair_count']==4
m['comparison_audit']={'script':'update602-audit-pairs.py','script_sha256':sha(HERE/'update602-audit-pairs.py'),
 'positive_log':log.name,'positive_log_sha256':sha(log),'receipt':audit.name,'receipt_sha256':sha(audit),
 'original_native_accepted':False}
m['status']='selected_cpu_proofs_rebound_flat_grade_original_unverified'
p.write_text(json.dumps(m,indent=2,ensure_ascii=False)+'\n');print(json.dumps({'cases':2,'manifest_sha256':sha(p)}))
