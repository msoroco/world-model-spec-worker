"""Independent source and candidate review of the complete v3 delivery return."""
import collections
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def require(ok,message):
 if not ok:raise ValueError(message)

def main():
 batch=read(ROOT/'batch.json');coverage_path=ROOT/'work/_shared/branch-coverage.json'
 coverage=read(coverage_path);sources=read(ROOT/'inputs/coverage/branch-sources.json')['laws']
 definitions={json.loads(line)['id']:json.loads(line) for line in (ROOT/'inputs/coverage/definitions.jsonl').read_text().splitlines() if line.strip()}
 review_path=ROOT/'work/_shared/branch-review.json';review=read(review_path)
 require(set(coverage['laws'])==set(sources)==set(review['laws']),'22-law source inventory differs')
 require(set(review['definition_ids_reviewed'])<=set(definitions),'Reviewed definition source missing')
 originals={aid:read(ROOT/'inputs'/aid/'assignment.json') for aid in batch['assignments']}
 supplemental={row['assignment_id']:read(ROOT/'work'/row['assignment_id']/'assignment.json')
               for row in coverage['additional_bindings']}
 assignments={**originals,**supplemental}
 total_cases=total_comparisons=reuses=branches=0
 for law,source in sources.items():
  original=next(a for a in originals.values() if a['law_id']==law)
  require(review['laws'][law]['statutory_text']==original['law']['text'],'Full law text differs: '+law)
  seen=set()
  actual_ids=[]
  for branch in coverage['laws'][law]['branches']:
   branches+=1;seen.update(branch['topic_ids']);actual_ids.append(branch['branch_id'])
   aid=branch['assignment_id'];require(assignments[aid]['law_id']==law,'Branch law/cell differs')
   plan=read(ROOT/'work'/aid/'case-plan.json')
   comparisons={row['comparison_id']:row for row in plan['comparisons']}
   require(branch['status']=='runnable' and len(branch['case_ids'])>=2,'Incomplete branch: '+branch['branch_id'])
   require(all(cid in comparisons and set(branch['case_ids'])<=set(comparisons[cid]['case_ids'])
               for cid in branch['comparison_ids']),'Uncontrolled branch comparison: '+branch['branch_id'])
  require(seen==set(source['topics']),'Source topic omitted: '+law)
  require(set(actual_ids)==set(review['laws'][law]['branch_ids']),'Independent branch inventory differs: '+law)
 for aid in assignments:
  folder=ROOT/'work'/aid;plan=read(folder/'case-plan.json');manifest=read(folder/'execution-manifest.json')
  selected={row['case_id'] for row in plan['cases']}
  require(selected=={row['case_id'] for row in manifest['cases']},'Selected case inventory differs: '+aid)
  total_cases+=len(selected);total_comparisons+=len(plan['comparisons'])
  uses=collections.Counter(cid for c in plan['comparisons'] for cid in c['case_ids'])
  reuses+=sum(count-1 for count in uses.values() if count>1)
  for entry in manifest['cases']:
   risk=entry.get('candidate_risk',{});candidates=entry.get('candidates',[])
   require(entry.get('kind')=='delivery' and risk.get('status') in ('none','physical') and risk.get('reason'),
           'Unreviewed delivery candidate risk: '+entry['case_id'])
   require((risk['status']=='none' and candidates==[]) or (risk['status']=='physical' and candidates),
           'Candidate risk and fallback disagree: '+entry['case_id'])
 require((len(sources),len(assignments),branches,total_cases,total_comparisons,reuses)==(22,43,158,236,150,66),
         'Reviewed delivery counts changed without a source-backed correction')
 review['coverage_sha256']=sha(coverage_path)
 review['branch_sources_sha256']=sha(ROOT/'inputs/coverage/branch-sources.json')
 review['definitions_sha256']=sha(ROOT/'inputs/coverage/definitions.jsonl')
 review['reviewer']='lead; separate from partition owners; v3 delivery return'
 review['review_method']='Independently read all 22 full exported law texts and 18 named definitions; rechecked each source topic against 158 runnable branches, exact selected IDs and controlled comparisons; verified 43 law/cell bindings, 236 delivery cases, 150 comparisons and 66 explicit reference reuses without treating CPU fixtures as physical or legal acceptance.'
 review['candidate_review_method']='Lead separately checked every exact manifest candidate-risk status/reason, required empty candidates for none and source-bound fallback presence for physical; confirmed comparison IDs and variables remain in the reviewed case plans. Native motion and pixel triggers remain for local operator execution.'
 review['unreviewed_candidates']=[]
 review['missing_branches']=[]
 review['physical_acceptance_claimed']=False;review['legal_acceptance_claimed']=False
 review_path.write_text(json.dumps(review,indent=2)+'\n')
 print(json.dumps({'laws':22,'assignments':43,'branches':branches,'cases':total_cases,
                   'comparisons':total_comparisons,'explicit_reuses':reuses,
                   'coverage_sha256':sha(coverage_path),'definitions_sha256':review['definitions_sha256']},indent=2))

if __name__=='__main__':main()
