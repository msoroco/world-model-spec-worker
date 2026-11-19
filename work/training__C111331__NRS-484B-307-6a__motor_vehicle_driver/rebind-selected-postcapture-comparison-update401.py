"""Bind current saved processing and independent controlled comparison logs."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
MANIFEST=HERE/'execution-manifest.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads(MANIFEST.read_text())
for e in m['cases']:
 suffix=e['case_id'].removeprefix(HERE.name+'__')
 log=HERE/'update400-selected-proofs'/suffix/'primary/process-saved.log'
 assert log.is_file() and json.loads(log.read_text())['passed'] is True
 e['post_capture']['test_log']=log.relative_to(HERE).as_posix()
 e['post_capture']['test_log_sha256']=sha(log)
for name in ('positive','fixed-negative','negative'):
 p=HERE/f'update401-comparison-{name}.log'
 assert p.is_file()
c=m['comparison_audit']
c.update({'script':'comparison_audit.py','script_sha256':sha(HERE/'comparison_audit.py'),
 'positive_log':'update401-comparison-positive.log',
 'positive_log_sha256':sha(HERE/'update401-comparison-positive.log'),
 'fixed_condition_negative_log':'update401-comparison-fixed-negative.log',
 'fixed_condition_negative_log_sha256':sha(HERE/'update401-comparison-fixed-negative.log'),
 'physical_negative_log':'update401-comparison-negative.log',
 'physical_negative_log_sha256':sha(HERE/'update401-comparison-negative.log')})
MANIFEST.write_text(json.dumps(m,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'cases':len(m['cases']),'manifest_sha256':sha(MANIFEST)}))
