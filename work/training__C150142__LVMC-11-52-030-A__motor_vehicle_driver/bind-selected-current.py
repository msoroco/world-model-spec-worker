"""Bind current text receipts for both exact red-curb diagnostic witnesses."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def bind(witness):
    if witness not in ('reference','contrast'):raise ValueError('Unknown witness')
    out=ROOT/('selected-'+witness+'-current-receipts')
    out.mkdir(exist_ok=True)
    case_id=ROOT.name+'__'+witness
    entries={}
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        manifest=ROOT/('execution-manifest-diagnostic-'+witness+
                       ('' if candidate=='primary' else '-'+candidate)+'.json')
        case=next(row for row in json.loads(manifest.read_text())['cases']
                  if row['case_id']==case_id)
        construction=ROOT/(case['construction'] if candidate=='primary' else
                           next(row['construction'] for row in case['candidates']
                                if row['id']==candidate))
        prefix=REPO/'.runtime-work'/('C150142-u020b-'+witness+'-'+candidate)
        sources={'compatibility':Path(str(prefix)+'-compat/compatibility.json'),
                 'saved':Path(str(prefix)+'-saved/v0001/processing.json'),
                 'result':Path(str(prefix)+'-saved/v0001/analysis/result.json'),
                 'analysis':Path(str(prefix)+'-saved/v0001/analysis/analysis-report.json'),
                 'offline_test':Path(str(prefix)+'-offline/offline.log'),
                 'negative_analysis':Path(str(prefix)+'-compat/negative-analysis.log')}
        folder=out/candidate;folder.mkdir(exist_ok=True)
        receipts={}
        for name,source in sources.items():
            target=folder/(name+('.log' if name.endswith(('test','analysis')) and name not in ('analysis',) else '.json'))
            shutil.copyfile(source,target)
            receipts[name]={'path':target.relative_to(ROOT).as_posix(),'sha256':sha(target)}
        compat=json.loads((folder/'compatibility.json').read_text())
        saved=json.loads((folder/'saved.json').read_text())
        result=json.loads((folder/'result.json').read_text())
        if not (compat['passed'] and saved['passed'] and
                saved['originals_preserved'] and not saved['missing_evidence'] and
                compat['construction_sha256']==sha(construction) and
                saved['analysis_revision']['construction_sha256']==sha(construction)):
            raise ValueError('Candidate proof incomplete or stale: '+witness+'/'+candidate)
        logs={stage:sha(ROOT/('update020b-'+witness+'-'+candidate+'-'+stage+'.log'))
              for stage in ('offline','compat','prepare','saved')}
        entries[candidate]={'manifest':manifest.relative_to(ROOT).as_posix(),
            'manifest_sha256':sha(manifest),
            'construction':construction.relative_to(ROOT).as_posix(),
            'construction_sha256':sha(construction),
            'fixture_recipe_sha256':sha(REPO/case['fixture_recipe']),
            'logs':logs,'receipts':receipts,
            'synthetic_red_stopped_frames':result['measured_values']['red_curb_stopped_frames']}
    index={'format':'c150142-current-candidate-cpu-index-v1','case_id':case_id,
           'status':'diagnostic_cpu_proven','original_native_observed':False,
           'physical_acceptance_claimed':False,'candidate_count':4,'candidates':entries}
    path=out/'proof-index.json';path.write_text(json.dumps(index,indent=2)+'\n')
    return {'index_sha256':sha(path),'witness':witness,
            'candidate_counts':{name:row['synthetic_red_stopped_frames']
                                for name,row in entries.items()}}

if __name__=='__main__':
    print(json.dumps([bind(w) for w in ('reference','contrast')],sort_keys=True))
