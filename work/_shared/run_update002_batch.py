"""Run independent exact-assignment CPU revalidation, never Native capture."""
import argparse,concurrent.futures,json,os,pathlib,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'work/_shared'))
from update002_tools import read,write,sha

def main():
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=['software','physical','all'],required=True);p.add_argument('--workers',type=int,default=4);p.add_argument('--assignments',nargs='*');a=p.parse_args()
 aids=a.assignments or [p.parent.name for p in sorted((ROOT/'work').glob('*/execution-manifest.json'))]
 env=dict(os.environ,TMPDIR=str(ROOT/'.runtime-work/tmp'),MPLCONFIGDIR=str(ROOT/'.runtime-work/mpl002'),XDG_CACHE_HOME=str(ROOT/'.runtime-work/cache002'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
 for key in ('TMPDIR','MPLCONFIGDIR','XDG_CACHE_HOME'):pathlib.Path(env[key]).mkdir(parents=True,exist_ok=True)
 def run(aid):
  log=ROOT/'work'/aid/'receipts'/('migration002-'+a.phase+'.log')
  command=[sys.executable,str(ROOT/'work/_shared/revalidate002.py'),'--assignment',aid,'--phase',a.phase]
  with log.open('w') as out:r=subprocess.run(command,cwd=ROOT,env=env,stdout=out,stderr=subprocess.STDOUT)
  return {'assignment_id':aid,'exit_code':r.returncode,'command':' '.join(command),'log':str(log.relative_to(ROOT)),'log_sha256':sha(log)}
 results=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
  for future in concurrent.futures.as_completed([pool.submit(run,aid) for aid in aids]):
   result=future.result();results.append(result);write(ROOT/'work/_shared'/('update002-'+a.phase+'-progress.json'),{'phase':a.phase,'finished_assignments':len(results),'total_assignments':len(aids),'results':results})
   print(result['assignment_id'],result['exit_code'],len(results),'/',len(aids),flush=True)
 failures=[r for r in results if r['exit_code']]
 if failures:print(json.dumps(failures,indent=2));raise SystemExit(1)
if __name__=='__main__':main()
