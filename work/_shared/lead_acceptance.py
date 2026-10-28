"""Lead continuation audit: submission and acceptance are independent outcomes."""
import collections,hashlib,json,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
def sha(path):return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
def run(command,log):
 p=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True);log.parent.mkdir(exist_ok=True);log.write_text(p.stdout)
 return dict(command=' '.join(command),exit_code=p.returncode,log=str(log.relative_to(ROOT)),sha256=sha(log))
def main():
 batch=json.loads((ROOT/'batch.json').read_text());report=dict(update=batch['update_version'],packages={},checks=[],implementation_gaps=[],external_requirements=[])
 for aid in batch['assignments']:
  folder=ROOT/'work'/aid;r=json.loads((folder/'result.json').read_text());plan=json.loads((folder/'case-plan.json').read_text());proposal=json.loads((folder/'proposals/cases.json').read_text());cases={c['case_id']:c for c in plan['cases']}
  for comp in plan['comparisons']:
   base=cases[comp['case_ids'][0]]['variable_assignments'];changed=set()
   for cid in comp['case_ids'][1:]:
    other=cases[cid]['variable_assignments'];changed|={k for k in set(base)|set(other) if base.get(k)!=other.get(k)}
   if changed!=set(comp['deliberate_differences']):report['implementation_gaps'].append(dict(assignment=aid,requirement='Comparison isolation',evidence=str(changed)+' != '+str(comp['deliberate_differences'])))
  for con in [folder/'construction.json',*sorted((folder/'constructions').glob('*.json'))]:
   d=json.loads(con.read_text())
   for f in d['files']:
    p=ROOT/f['source'] if f.get('source') else folder/f['path']
    if p.read_text()!=f['content']:report['implementation_gaps'].append(dict(assignment=aid,requirement='Inline/source equality',evidence=str(con.relative_to(ROOT))+':'+f['path']))
  requirements=r.get('requirements',r.get('externally_blocked_requirements',r.get('gaps',[])))
  if r['status']=='blocked' and not requirements:report['implementation_gaps'].append(dict(assignment=aid,requirement='Blocked package lacks structured external requirement',evidence=r.get('reason')))
  if isinstance(requirements,list):
   for req in requirements:
    if not isinstance(req,dict) or any(k not in req for k in ('requirement','category','evidence','next_action','requires_live_execution')):report['implementation_gaps'].append(dict(assignment=aid,requirement='Malformed structured requirement',evidence=req));continue
    if req['category'] not in ('implementation','live_measurement','external_asset') or not isinstance(req['requires_live_execution'],bool) or not req['evidence'] or not req['next_action']:report['implementation_gaps'].append(dict(assignment=aid,requirement='Invalid external requirement evidence/category',evidence=req));continue
    if req.get('status') in ('resolved','complete','implemented','verified'):continue
    target='implementation_gaps' if req['category']=='implementation' else 'external_requirements'
    report[target].append(dict(assignment=aid,**req))
  if r['status']=='partial':report['implementation_gaps'].append(dict(assignment=aid,requirement='Partial checkpoint cannot finish',evidence=r.get('reason')))
  report['packages'][aid]=dict(status=r['status'],reason=r.get('reason'),case_count=len(cases))
 checks=[('shared-tests',[sys.executable,'-m','unittest','discover','-s','work/_shared/tests']),('materialized-bundles',[sys.executable,'work/_shared/materialize.py','--all']),('repo-tests',[sys.executable,'-m','unittest','discover','-s','tests'])]
 for name in ('intersection','judgment','numeric'):
  checks.extend([(name+'-check',[sys.executable,'examples/'+name+'/runner.py','--check']),(name+'-tests',[sys.executable,'-m','unittest','discover','-s','examples/'+name+'/tests'])])
 checks.extend([('update-status',[sys.executable,'update_status.py']),('submission',[sys.executable,'worker_check.py','--complete']),('preparation-acceptance',[sys.executable,'worker_check.py','--require-ready'])])
 for tag,command in checks:
  record=run(command,ROOT/'work/_shared/logs'/(tag+'.log'));record['check']=tag;report['checks'].append(record);print(tag,record['exit_code'],flush=True)
 report['status_counts']=dict(collections.Counter(x['status'] for x in report['packages'].values()));report['submission_passed']=next(c['exit_code']==0 for c in report['checks'] if c['check']=='submission');report['preparation_accepted']=next(c['exit_code']==0 for c in report['checks'] if c['check']=='preparation-acceptance')
 report['terminal_external_blockers_only']=not report['implementation_gaps'] and all(p['status'] in ('ready','blocked') for p in report['packages'].values())
 (ROOT/'work/_shared/lead-acceptance.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('status_counts','submission_passed','preparation_accepted','terminal_external_blockers_only')},indent=2))
 return 0 if report['terminal_external_blockers_only'] and all(c['exit_code']==0 for c in report['checks'] if c['check']!='preparation-acceptance') else 1
if __name__=='__main__':raise SystemExit(main())
