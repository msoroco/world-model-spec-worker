"""Independently audit twelve pinned-runtime sightline source and saved chains."""
import copy
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SUFFIXES=('below_500_ft','at_500_ft','above_500_ft')
CANDIDATES=('primary','fallback1','fallback2','fallback3')
CAMERAS=('overview','approach','reference_corner','driver_reference')
CHECKS={'actual_analysis','native_validation','mandatory_observations','lean_decoder',
        'render','final_decode','acquisition_unchanged','derived_outputs_rebuilt',
        'four_camera_sources','selected_measurements','negative_case_source'}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def require(ok,msg):
    if not ok:raise ValueError(msg)

def audit(progress=None):
    progress=progress or read(HERE/'current-runtime-matrix-progress.json')
    manifest=read(HERE/'current-runtime-reproof-manifest.json')
    current=sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json')
    require(progress['runtime_manifest_sha256']==manifest['runtime_manifest_sha256']==current and
            progress['manifest_sha256']==sha(HERE/'current-runtime-reproof-manifest.json') and
            progress['completed']==progress['required']==12 and len(progress['rows'])==12,
            'Pinned-runtime matrix incomplete')
    rows={(row['case_id'],row['candidate_id']):row for row in progress['rows']}
    require(len(rows)==12 and [e['case_id'].rsplit('__',1)[-1] for e in manifest['cases']]==list(SUFFIXES),
            'Selected cases changed')
    limits=[];roads=set();traces=set();evidences=set();attempts=[]
    for entry in manifest['cases']:
        case=entry['case_id'];suffix=case.rsplit('__',1)[-1]
        obstruction=read(HERE/'draft-sightline'/suffix/'obstruction.json')
        limits.append(round(1000*math.acos(obstruction['inner_radius_m']/500)/.3048))
        for candidate in CANDIDATES:
            selected=entry if candidate=='primary' else next(c for c in entry['candidates'] if c['id']==candidate)
            row=rows[(case,candidate)];proof=HERE/row['proof_dir']
            require(sha(HERE/selected['construction'])==selected['construction_sha256']==row['construction_sha256'],
                    'Selected construction changed')
            compat=read(proof/'compatibility.json');saved=read(proof/'saved-processing.json')
            require(sha(proof/'compatibility.json')==row['compatibility_sha256'] and
                    sha(proof/'saved-processing.json')==row['saved_sha256'] and
                    compat['passed'] is True and compat['runtime_manifest_sha256']==current and
                    compat['construction_sha256']==selected['construction_sha256'] and
                    compat['case_id']==case and compat['candidate_id']==candidate and
                    CHECKS<=set(compat['checks']) and
                    compat['log_sha256']==sha(proof/'analysis.log') and
                    compat['negative_log_sha256']==sha(proof/'negative-analysis.log') and
                    compat['negative_error_contains'] in (proof/'negative-analysis.log').read_text(),
                    'Positive/negative compatibility differs')
            require(saved['passed'] is True and saved['recorded_only'] is True and
                    saved['originals_preserved'] is True and saved['missing_evidence'] is False and
                    saved['case_id']==case and saved['candidate_id']==candidate and
                    saved['native_revision']['construction_sha256']==selected['construction_sha256'] and
                    saved['timestamp_joins']['frames']==480 and saved['final_video_checks']['passed'] is True and
                    saved['physical_acceptance_claimed'] is False and saved['legal_acceptance_claimed'] is False,
                    'Recorded-only saved proof differs')
            recipe_path=ROOT/entry['fixture_recipe'] if candidate=='primary' else HERE/f'update043-{suffix}-{candidate}-recipe.json'
            recipe=read(recipe_path);source=read(ROOT/recipe['generator']['source'])
            context=json.loads(source['files']['native-construction-context.json'])
            require(context['case_id']==case and context['candidate_id']==candidate and
                    compat['fixture_recipe_sha256']==sha(recipe_path) and
                    recipe['generator']['sha256']==sha(ROOT/recipe['generator']['source']),
                    'Candidate-specific source changed')
            roads.add(hashlib.sha256(source['files']['road.xodr'].encode()).hexdigest())
            traces.add(hashlib.sha256(source['files']['trace.jsonl'].encode()).hexdigest())
            evidences.add(hashlib.sha256(source['files']['capture/evidence.jsonl'].encode()).hexdigest())
            matches=[p for p in (ROOT/'.runtime-work').glob(f'c104538-current-{suffix}-{candidate}-*-compat')
                     if (p/'compatibility.json').is_file() and sha(p/'compatibility.json')==row['compatibility_sha256']]
            require(len(matches)==1,'Matching source attempt missing or ambiguous')
            attempt=matches[0]
            require(all(sha(attempt/(name+'.mkv'))==saved['original_source_hashes'].get(name+'.mkv')
                        for name in CAMERAS),'Source cameras changed')
            attempts.append({'case_id':case,'candidate_id':candidate,'construction_sha256':row['construction_sha256'],
                             'compatibility_sha256':row['compatibility_sha256'],'saved_sha256':row['saved_sha256'],
                             'source_camera_sha256':{name:sha(attempt/(name+'.mkv')) for name in CAMERAS}})
    require(limits==[450,500,550] and len(roads)==len(traces)==len(evidences)==1,
            'Boundary or controlled context changed')
    return {'format':'c104538-current-runtime-independent-source-audit-v1','passed':True,
            'runtime_manifest_sha256':current,'attempts':attempts,'selected_cases':3,
            'candidate_chains':12,'limits_ft':limits,'controlled_context':True,
            'original_native_proven':False,'accepted_comparisons':0}

def main():
    result=audit();progress=read(HERE/'current-runtime-matrix-progress.json');rejected=0
    for damage in ('missing_candidate','stale_construction','stale_runtime'):
        changed=copy.deepcopy(progress)
        if damage=='missing_candidate':changed['rows'].pop();changed['completed']-=1
        elif damage=='stale_construction':changed['rows'][0]['construction_sha256']='0'*64
        else:changed['runtime_manifest_sha256']='0'*64
        try:audit(changed)
        except (ValueError,KeyError):rejected+=1
        else:raise AssertionError('Corrupt matrix accepted: '+damage)
    result['negative_rejections']=rejected
    path=HERE/'current-runtime-selected-source-audit.json';path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'candidate_chains':12,'negative_rejections':rejected}))

if __name__=='__main__':main()
