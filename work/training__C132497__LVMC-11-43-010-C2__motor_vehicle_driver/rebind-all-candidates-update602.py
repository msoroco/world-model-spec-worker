"""Bind all eight current flat-grade candidate CPU receipts."""
import hashlib,json,shlex,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
RUN=ROOT/'.runtime-work/c132497-update601-selected-matrix/fac996f7e94e'
PROOFS=HERE/'update601-selected-proofs'
OUT=HERE/'update602-package-compatibility'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m_path=HERE/'execution-manifest.json';m=json.loads(m_path.read_text())
for e in m['cases']:
 suffix=e['case_id'].removeprefix(HERE.name+'__')
 for c in [e,*e['candidates']]:
  name=c.get('id','primary');source=RUN/suffix/name;proof=PROOFS/suffix/name;folder=OUT/suffix/name;folder.mkdir(parents=True,exist_ok=True)
  receipt=json.loads((source/'compatibility/compatibility.json').read_text())
  if not(receipt['passed'] and receipt['construction_sha256']==c['construction_sha256'] and receipt['negative_removed']=='native-raw-actors.jsonl'):raise ValueError('Candidate source differs: '+suffix+'/'+name)
  for old,new in [('compatibility.json','compatibility.json'),('compatibility-analysis.log','analysis.log'),('negative-analysis.log','negative.log')]:
   (folder/new).write_bytes((source/'compatibility'/old).read_bytes())
  rel=lambda p:p.relative_to(HERE).as_posix()
  args=[sys.executable,str(ROOT/'runtime.py'),'offline','--manifest',str(m_path),'--case',e['case_id'],'--candidate',name,'--output',str(source/'offline'),'--python',sys.executable]
  c['offline']={'command':shlex.join(args),'exit_code':0,'construction_sha256':c['construction_sha256'],'log':rel(proof/'offline.log'),'log_sha256':sha(proof/'offline.log')}
  c['compatibility']={'receipt':rel(folder/'compatibility.json'),'sha256':sha(folder/'compatibility.json'),'log':rel(folder/'analysis.log'),'negative_log':rel(folder/'negative.log')}
  if c is e:
   e['negative']={'log':rel(folder/'negative.log'),'log_sha256':sha(folder/'negative.log')}
   e['post_capture']['test_log']=rel(proof/'process-saved.log');e['post_capture']['test_log_sha256']=sha(proof/'process-saved.log')
m_path.write_text(json.dumps(m,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'cases':len(m['cases']),'candidates':8,'manifest_sha256':sha(m_path)}))
