"""Retain text receipts for the current four exact reference constructions."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'selected-reference-receipts'
CASE=ROOT.name+'__reference'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    OUT.mkdir(exist_ok=True)
    entries={}
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        manifest=ROOT/('execution-manifest-diagnostic-reference.json' if candidate=='primary'
            else 'execution-manifest-diagnostic-reference-'+candidate+'.json')
        contents=json.loads(manifest.read_text())
        case=next(item for item in contents['cases'] if item['case_id']==CASE)
        construction=ROOT/(case['construction'] if candidate=='primary' else
            next(item['construction'] for item in case['candidates'] if item['id']==candidate))
        prefix=ROOT.parents[1]/'.runtime-work'/('C150142-u019c-'+candidate)
        sources={'compatibility':prefix.with_name(prefix.name+'-compat')/'compatibility.json',
                 'saved':prefix.with_name(prefix.name+'-saved')/'v0001/processing.json',
                 'result':prefix.with_name(prefix.name+'-saved')/'v0001/analysis/result.json',
                 'analysis':prefix.with_name(prefix.name+'-saved')/'v0001/analysis/analysis-report.json'}
        folder=OUT/candidate;folder.mkdir(exist_ok=True)
        copied={}
        for name,source in sources.items():
            target=folder/(name+'.json')
            shutil.copyfile(source,target)
            copied[name]={'path':target.relative_to(ROOT).as_posix(),
                          'sha256':sha(target)}
        for name,source in {'offline_test':prefix.with_name(prefix.name+'-offline')/'offline.log',
                            'negative_analysis':prefix.with_name(prefix.name+'-compat')/'negative-analysis.log'}.items():
            target=folder/(name+'.log')
            shutil.copyfile(source,target)
            copied[name]={'path':target.relative_to(ROOT).as_posix(),
                          'sha256':sha(target)}
        compat=json.loads((folder/'compatibility.json').read_text())
        saved=json.loads((folder/'saved.json').read_text())
        result=json.loads((folder/'result.json').read_text())
        if compat['passed'] is not True or saved['passed'] is not True or \
           saved['missing_evidence'] is not False or \
           saved['originals_preserved'] is not True or \
           compat['construction_sha256']!=sha(construction) or \
           saved['analysis_revision']['construction_sha256']!=sha(construction):
            raise ValueError('Candidate proof is incomplete or stale: '+candidate)
        entries[candidate]={'manifest':manifest.relative_to(ROOT).as_posix(),
            'manifest_sha256':sha(manifest),
            'construction':construction.relative_to(ROOT).as_posix(),
            'construction_sha256':sha(construction),
            'fixture_recipe_sha256':sha(ROOT.parents[1]/case['fixture_recipe']),
            'logs':{stage:sha(ROOT/('update019c-'+candidate+'-'+stage+'.log'))
                    for stage in ('offline','compat','prepare','saved')},
            'receipts':copied,
            'synthetic_red_stopped_frames':result['measured_values']['red_curb_stopped_frames']}
    index={'format':'c150142-reference-candidate-cpu-index-v1',
           'case_id':CASE,'status':'diagnostic_cpu_proven',
           'original_native_observed':False,'physical_acceptance_claimed':False,
           'candidate_count':4,'candidates':entries}
    path=OUT/'proof-index.json';path.write_text(json.dumps(index,indent=2)+'\n')
    return {'index_sha256':sha(path),'candidates':{
        name:value['synthetic_red_stopped_frames'] for name,value in entries.items()}}


if __name__=='__main__':print(json.dumps(bind(),sort_keys=True))
