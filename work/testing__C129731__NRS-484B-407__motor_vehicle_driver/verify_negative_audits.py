"""Assert direct negative audit proofs while preserving their exit-1 evidence."""
import hashlib,json,sys
from pathlib import Path
folder=Path(__file__).resolve().parent
manifest=json.loads((folder/'execution-manifest.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for case in manifest['cases']:
 d=case['delivery_acceptance'];p=folder/d['negative_log']
 assert d['negative_exit_code']==1,case['case_id']
 assert sha(p)==d['negative_log_sha256'],case['case_id']
 assert d['negative_expected_error'] in p.read_text(),case['case_id']
 assert case['case_id'] in d['negative_command'],case['case_id']
 print('verified negative audit',case['case_id'],d['negative_expected_error'],d['negative_log_sha256'])
