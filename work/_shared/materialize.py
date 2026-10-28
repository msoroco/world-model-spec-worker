"""Materialize each canonical case payload, then run offline checks and its tests."""
import argparse,hashlib,json,os,pathlib,shutil,subprocess,sys,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def materialize(proposal,destination):
 proposal=pathlib.Path(proposal);data=json.loads(proposal.read_text());destination=pathlib.Path(destination);destination.mkdir(parents=True,exist_ok=True)
 for entry in data['files']:
  rel=pathlib.PurePosixPath(entry['path'])
  if rel.is_absolute() or '..' in rel.parts:raise ValueError('Escaping inline file')
  if entry.get('source'):
   source=(ROOT/entry['source']).resolve()
   if ROOT not in source.parents or source.read_text()!=entry['content']:raise ValueError('Stale shared source '+entry['source'])
  out=destination/rel;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(entry['content'])
 (destination/'construction.json').write_text(json.dumps(data,indent=2)+'\n')
 return data

def validate_assignment(aid):
 w=ROOT/'work'/aid;proposals=[w/'construction.json',*sorted((w/'constructions').glob('*.json'))];records=[]
 for proposal in proposals:
  with tempfile.TemporaryDirectory(prefix='materialized-',dir=str(ROOT/'work/_shared')) as temp:
   bundle=pathlib.Path(temp);data=materialize(proposal,bundle)
   if (w/'tests').is_dir():shutil.copytree(w/'tests',bundle/'tests',ignore=shutil.ignore_patterns('__pycache__'))
   env=dict(os.environ,PYTHONPATH=str(bundle)+os.pathsep+str(ROOT/'runtime/python')+os.pathsep+str(ROOT/'runtime'),PYTHONDONTWRITEBYTECODE='1')
   for tag,cmd in [('check',[sys.executable,'runner.py','--check']),('tests',[sys.executable,'-m','unittest','discover','-s','tests'])]:
    p=subprocess.run(cmd,cwd=bundle,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True)
    log=w/'logs'/('bundle-'+proposal.stem+'-'+tag+'.log');log.parent.mkdir(exist_ok=True);log.write_text(p.stdout)
    records.append(dict(case_id=data['case_id'],proposal=str(proposal.relative_to(ROOT)),proposal_sha256=sha(proposal),command=' '.join(cmd),exit_code=p.returncode,log=str(log.relative_to(w)),sha256=sha(log),materialized_before_test=True))
 return records

def main():
 p=argparse.ArgumentParser();p.add_argument('--assignment',action='append');p.add_argument('--all',action='store_true');a=p.parse_args();batch=json.loads((ROOT/'batch.json').read_text());ids=list(batch['assignments']) if a.all else a.assignment
 if not ids:p.error('--assignment ID or --all required')
 failures=[]
 for aid in ids:
  records=validate_assignment(aid);w=ROOT/'work'/aid;(w/'materialized-tests.json').write_text(json.dumps(records,indent=2)+'\n');bad=[r for r in records if r['exit_code']];failures+=bad;print(aid,len(records),'commands',len(bad),'failures')
 return bool(failures)
if __name__=='__main__':raise SystemExit(main())
