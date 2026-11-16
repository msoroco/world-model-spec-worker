"""Bind exact contrast matrix and settled full gate to the truthful handoff."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
RESULT=ROOT/'result.json'
HANDOFF=ROOT/'HANDOFF.md'
REPORT=REPO/'work/_shared/RETURN-REPORT.md'
GATE=REPO/'work/_shared/update056-full-strict.log'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def proof(command,log):return {'command':command,'exit_code':0,'log':log,'sha256':sha(ROOT/log)}

assignment=ROOT.name;base='work/'+assignment;case=assignment+'__contrast'
new=[];rows=[]
for candidate in ('primary','fallback1','fallback2','fallback3'):
    manifest=(base+'/execution-manifest-contrast-draft.json' if candidate=='primary'
              else base+'/execution-manifest-diagnostic-contrast-'+candidate+'.json')
    prefix='.runtime-work/c146314-210-2-contrast-'+candidate
    offline='update056b-contrast-'+candidate+'-offline.log'
    compat='update056-contrast-'+candidate+'-compat.log'
    saved='update056-contrast-'+candidate+'-saved.log'
    receipt=REPO/(prefix+'-compat-update056/compatibility.json')
    processed=REPO/(prefix+'-fresh-update056-saved/v0001/processing.json')
    a=json.loads(receipt.read_text());b=json.loads(processed.read_text())
    assert a['passed'] and a['candidate_id']==candidate and 'negative_case_source' in a['checks']
    assert b['passed'] and not b['missing_evidence'] and b['originals_preserved']
    assert b['timestamp_joins']['frames']==240 and b['final_video_checks']['passed']
    new.append(proof(
        f'.venv-cpu/bin/python runtime.py offline --manifest {base}/execution-manifest-contrast-draft.json '
        f'--case {case} --candidate {candidate} --output {prefix}-offline-update056b '
        f'--python {REPO}/.venv-cpu/bin/python',offline))
    new.append(proof(
        f'.venv-cpu/bin/python runtime.py compatibility --manifest {manifest} --case {case} '
        f'--candidate {candidate} --output {prefix}-compat-update056 '
        '--library runtime/pipeline/library --validator .runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck',compat))
    new.append(proof(
        f'.venv-cpu/bin/python {base}/run-reference-fallback-saved.py {candidate} contrast',saved))
    rows.append(f'`{candidate}` offline/compatibility/saved logs SHA-256 '
                f'`{sha(ROOT/offline)}` / `{sha(ROOT/compat)}` / `{sha(ROOT/saved)}`; '
                f'compatibility receipt `{sha(receipt)}`, saved receipt `{sha(processed)}`.')
value=json.loads(RESULT.read_text())
value['status']='partial';value['readiness_kind']=None;value['cases_selected']=0
value['reason']=(
    'Both right-pass cases now have an exact selected primary and three distinct fallbacks. All eight '
    'pass pinned offline, candidate-specific positive/negative compatibility and fresh actual saved '
    'processing with four source videos, Core/Lean, 240 frame joins, preserved acquisition, no missing '
    'evidence and final decode. Canonical semantic stage proposals, one unified delivery manifest, '
    'independent selected physical/delivery and comparison audits, and scoped strict readiness remain '
    'worker-owned CPU work. The batch strict gate also rejects an unchanged generated frozen-runtime '
    'output. No original Native motion, physical clearance acceptance, legal safety verdict or accepted '
    'recording is claimed.')
old={row['log']:row for row in value['tests']};old.update({row['log']:row for row in new})
value['tests']=list(old.values())
RESULT.write_text(json.dumps(value,indent=2)+'\n')
paragraph='\n### Update 056 contrast selected CPU matrix and settled gate\n\n'
paragraph+=('The contrast case `'+case+'` now has selected primary and three distinct fallback '
            'constructions. Each passes current pinned offline, positive/negative compatibility with '
            'a candidate-specific source-hashed fixture, and fresh actual saved processing. All saved '
            'receipts report no missing evidence, acquisition preserved, 240 joined frames and full '
            'final decode. '+' '.join(rows)+'\n\n')
paragraph+=('The full strict batch gate exits 1 at `Unapproved output: '
            'runtime/pipeline/runs/scenario_pipeline/inputs/shared/manifest.json` '
            f'(`work/_shared/update056-full-strict.log`, SHA-256 `{sha(GATE)}`). '
            'That frozen runtime file was not edited. The earlier scoped ordinary gate exits 0; '
            f'its log SHA-256 is `{sha(ROOT/"update056-scoped-complete.log")}`. '
            'Scoped strict exits 1 because C146314 remains partial; '
            f'its log SHA-256 is `{sha(ROOT/"update056-scoped-strict.log")}`. '
            'One unified canonical delivery manifest, canonical semantic stages, independent selected '
            'delivery/physical and comparison audits, and scoped strict readiness remain unfinished '
            'worker-owned CPU work. No original CARLA movement, measured real clearance or legal safety '
            'finding has been accepted.\n')
with HANDOFF.open('a') as stream:stream.write(paragraph)
with REPORT.open('a') as stream:stream.write(paragraph)
print('contrast-checkpoint-written',len(new))
