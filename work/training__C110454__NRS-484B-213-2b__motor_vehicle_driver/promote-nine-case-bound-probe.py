"""Promote source-proven intersection pair after eight-chain draft and static validation."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
canonical=HERE/'execution-manifest.json';probe=HERE/'update040-nine-case-bound-probe-manifest.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
old=json.loads(canonical.read_text());new=json.loads(probe.read_text())
assert len(old['cases'])==7 and len(new['cases'])==9
assert [e['case_id'] for e in new['cases'][:7]]==[e['case_id'] for e in old['cases']]
assert {e['case_id'].rsplit('__',1)[-1] for e in new['cases'][7:]}=={'reference','contrast'}
assert len(json.loads((HERE/'update040-intersection-draft-index.json').read_text())['results'])==8
snapshot=HERE/'update040-pre-nine-case-manifest.json';assert not snapshot.exists();snapshot.write_bytes(canonical.read_bytes())
canonical.write_bytes(probe.read_bytes())
print(json.dumps({'cases':9,'candidates':36,'manifest_sha256':sha(canonical),'acceptance_rebind_pending':True}))
