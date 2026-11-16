"""Record fallback saved and contrast offline receipts, preserving partial status."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
RESULT=ROOT/'result.json'
HANDOFF=ROOT/'HANDOFF.md'
REPORT=REPO/'work/_shared/RETURN-REPORT.md'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def proof(command,log):return {'command':command,'exit_code':0,'log':log,'sha256':sha(ROOT/log)}

assignment=ROOT.name
base='work/'+assignment
case=assignment+'__reference'
new=[]
for n in (1,2,3):
    candidate='fallback'+str(n)
    manifest=base+'/execution-manifest-diagnostic-'+candidate+'.json'
    compat=REPO/('.runtime-work/c146314-210-2-reference-'+candidate+'-compat-update056/compatibility.json')
    saved=REPO/('.runtime-work/c146314-210-2-reference-'+candidate+'-fresh-update056-saved/v0001/processing.json')
    a=json.loads(compat.read_text());b=json.loads(saved.read_text())
    assert a['passed'] and a['candidate_id']==candidate and 'negative_case_source' in a['checks']
    assert b['passed'] and not b['missing_evidence'] and b['originals_preserved']
    assert b['timestamp_joins']['frames']==240 and b['final_video_checks']['passed']
    new.append(proof(
        f'.venv-cpu/bin/python runtime.py compatibility --manifest {manifest} --case {case} '
        f'--candidate {candidate} --output .runtime-work/c146314-210-2-reference-{candidate}-compat-update056 '
        '--library runtime/pipeline/library --validator .runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck',
        'update056-reference-'+candidate+'-compat.log'))
    new.append(proof(f'.venv-cpu/bin/python {base}/run-reference-fallback-saved.py {candidate}',
                     'update056-reference-'+candidate+'-saved.log'))
new.append(proof(
    f'.venv-cpu/bin/python runtime.py offline --manifest {base}/execution-manifest-contrast-draft.json '
    f'--case {assignment}__contrast --output .runtime-work/c146314-210-2-contrast-primary-offline-update056 '
    f'--python {REPO}/.venv-cpu/bin/python',
    'update056-contrast-primary-offline.log'))
value=json.loads(RESULT.read_text())
value['status']='partial';value['readiness_kind']=None;value['cases_selected']=0
value['reason']=(
    'Reference primary and all three distinct fallbacks pass exact selected offline, positive/negative '
    'pinned compatibility and fresh actual saved processing using candidate-specific synthetic source '
    'recipes; each saved receipt has 240 joined frames, preserved sources, no missing evidence and final '
    'video decode. The contrast selected primary passes offline only. Contrast compatibility/saved and '
    'three fallbacks, canonical semantic stages, independent selected physical/delivery and comparison '
    'audits, and strict readiness remain worker-owned CPU work. Candidate-specific diagnostic manifests '
    'are draft test binders and still need a canonical delivery manifest. No original Native motion, '
    'physical clearance acceptance or legal safety verdict is claimed.')
old={row['log']:row for row in value['tests']};old.update({row['log']:row for row in new})
value['tests']=list(old.values())
RESULT.write_text(json.dumps(value,indent=2)+'\n')
rows=[]
for n in (1,2,3):
    name='fallback'+str(n)
    rows.append(f'`{name}` compatibility log SHA-256 `{sha(ROOT/("update056-reference-"+name+"-compat.log"))}`, '
                f'fresh saved log SHA-256 `{sha(ROOT/("update056-reference-"+name+"-saved.log"))}`; '
                f'compatibility receipt SHA-256 `{sha(REPO/(".runtime-work/c146314-210-2-reference-"+name+"-compat-update056/compatibility.json"))}`, '
                f'saved receipt SHA-256 `{sha(REPO/(".runtime-work/c146314-210-2-reference-"+name+"-fresh-update056-saved/v0001/processing.json"))}`.')
paragraph='\n### Update 056 further selected CPU proof\n\n'
paragraph+='The three reference fallbacks each pass pinned positive/negative `runtime.py compatibility` with their own source-hashed recipe and fresh actual `runtime.py process-saved`. All three saved receipts report `passed=true`, `missing_evidence=false`, original sources preserved, 240 frame joins and full final decode. '+ ' '.join(rows)+'\n\n'
paragraph+=('The contrast selected primary at `selected-primary/contrast/construction.json` matches its canonical case proposal and passes pinned offline (`update056-contrast-primary-offline.log`, SHA-256 `'+sha(ROOT/'update056-contrast-primary-offline.log')+'`). Contrast compatibility/saved, its three fallbacks, canonical semantic stages and independent audits remain unfinished CPU work. The fallback diagnostic manifests bind candidate-specific source recipes for these proofs; canonical delivery binding is still pending. Status remains `partial`, with zero fully selected cases. No original CARLA motion or NRS safety conclusion is claimed.\n')
with HANDOFF.open('a') as stream:stream.write(paragraph)
with REPORT.open('a') as stream:stream.write(paragraph)
print('late-checkpoint-written',len(new))
