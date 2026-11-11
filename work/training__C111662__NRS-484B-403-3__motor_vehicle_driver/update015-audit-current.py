"""Independent hash and comparison audit of current U-turn diagnostic CPU proofs."""
import hashlib
import json
import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parent
NATIVE=ROOT/'native'
CASES=('reference','contrast','divided_reference','divided_opening')
CANDIDATES=('primary','fallback1','fallback2','fallback3')
REQUIRED={'actual_analysis','native_validation','mandatory_observations','lean_decoder',
          'render','final_decode','four_camera_sources','selected_measurements',
          'negative_case_source','acquisition_unchanged','derived_outputs_rebuilt'}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):return json.loads(Path(path).read_text())


def inspect(case,candidate,entry):
    case_id=ROOT.name+'__'+case
    if candidate=='primary':
        summary=next(row for row in read(ROOT/'update015-current-primary-matrix.json')['results']
                     if row['case_id']==case_id)
        folder=ROOT/'update015-current-primary'/case
        manifest=ROOT/'draft-execution-manifest.json'
        selected=entry
    else:
        folder=ROOT/'update015-current-fallback'/case/candidate
        summary=read(folder/'summary.json')
        manifest=ROOT/f'draft-execution-manifest-{case}-{candidate}.json'
        selected=next(row for row in entry['candidates'] if row['id']==candidate)
    construction=ROOT/selected['construction']
    if sha(construction)!=selected['construction_sha256'] or summary['construction_sha256']!=sha(construction):
        raise ValueError('Construction hash mismatch: '+case+'/'+candidate)
    packaged=read(construction)
    files={f['path']:f['content'] for f in packaged['files']}
    config=json.loads(files['config.json'])
    frontage=json.loads(files['frontage-plan.json'])
    if frontage!=read(NATIVE/'frontage-plan.json') or frontage['district_designation_verified'] is not False:
        raise ValueError('Frontage plan source or uncertainty changed: '+case+'/'+candidate)
    if files['frontage.py']!=files[f'work/{ROOT.name}/native/frontage.py']:
        raise ValueError('Frontage implementation differs across package paths')
    capture_name='capture_divided.py' if case.startswith('divided_') else 'capture.py'
    capture_code=files[f'work/{ROOT.name}/native/{capture_name}']
    capture=next(n for n in ast.parse(capture_code).body
                 if isinstance(n,ast.FunctionDef) and n.name=='capture')
    calls={n.func.id for n in ast.walk(capture) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
    if 'spawn_and_measure' not in calls or 'authored_plan' not in calls:
        raise ValueError('Native capture lacks physical frontage construction')
    if config['case_id']!=case_id or config['candidate_id']!=candidate:
        raise ValueError('Candidate identity mismatch')
    compatibility=read(folder/'compatibility.json')
    processing=read(folder/'processing.json')
    raw=NATIVE/('divided-opening' if case.startswith('divided_') else '')/'synthetic'/case/candidate/'raw.json'
    if (compatibility.get('passed') is not True or compatibility.get('candidate_id')!=candidate
        or compatibility.get('construction_sha256')!=sha(construction)
        or not REQUIRED<=set(compatibility.get('checks',[]))
        or compatibility['fixture_manifest']['raw.json']!=sha(raw)
        or compatibility['negative_removed']!='raw.json'
        or compatibility['negative_error_contains'] not in (folder/'negative-analysis.log').read_text()):
        raise ValueError('Compatibility receipt/source mismatch: '+case+'/'+candidate)
    if (processing.get('passed') is not True or processing.get('candidate_id')!=candidate
        or processing.get('originals_preserved') is not True
        or processing.get('physical_acceptance_claimed') is not False
        or processing.get('legal_acceptance_claimed') is not False
        or processing.get('native_revision',{}).get('construction_sha256')!=sha(construction)):
        raise ValueError('Saved-processing receipt mismatch: '+case+'/'+candidate)
    if (summary['compatibility_sha256']!=sha(folder/'compatibility.json')
        or summary['processing_sha256']!=sha(folder/'processing.json')
        or summary['negative_log_sha256']!=sha(folder/'negative-analysis.log')):
        raise ValueError('Durable receipt hash mismatch: '+case+'/'+candidate)
    if candidate!='primary':
        variant=read(manifest)
        case_entry=next(row for row in variant['cases'] if row['case_id']==case_id)
        recipe=ROOT/f'update015-current-{case}-{candidate}-recipe.json'
        if variant['diagnostic_candidate']!=candidate or case_entry['fixture_recipe']!=recipe.relative_to(ROOT.parents[1]).as_posix():
            raise ValueError('Fallback diagnostic recipe mismatch')
        if compatibility['fixture_recipe_sha256']!=sha(recipe):
            raise ValueError('Fallback recipe hash mismatch')
    return config


def main():
    manifest=read(ROOT/'draft-execution-manifest.json')
    witness=ROOT.parents[1]/'inputs'/ROOT.name/'witnesses.json'
    planned=read(ROOT/'case-plan.json')
    witness_source=next(row for row in planned['sources'] if row['path'].endswith('/witnesses.json'))
    if sha(witness)!=witness_source['sha256']:
        raise ValueError('Frozen conditional witness changed')
    contexts=' '.join(read(witness)[0]['witness']['required_context']).lower()
    if not all(term in contexts for term in ('300-foot','600-foot','business')):
        raise ValueError('Frontage construction lacks frozen witness threshold')
    configs={}
    for entry in manifest['cases']:
        case=entry['case_id'].rsplit('__',1)[-1]
        for candidate in CANDIDATES:
            configs[(case,candidate)]=inspect(case,candidate,entry)
    for case in CASES:
        primary=configs[(case,'primary')]
        for candidate in CANDIDATES[1:]:
            changed=configs[(case,candidate)]
            for key in ('assignment_id','assignment_sha256','case_id','road_sha256','ego_blueprint',
                        'frames','rate_hz','source_text'):
                if changed.get(key)!=primary.get(key):
                    raise ValueError('Fallback changed fixed source: '+case+'/'+candidate+'/'+key)
            distinct = {
                'fallback1': changed['requested_approach_speed_mps'] != primary['requested_approach_speed_mps']
                             and changed['tracks_sha256'] != primary['tracks_sha256'],
                'fallback2': changed['camera_policy'] != primary['camera_policy'],
                'fallback3': changed['pre_turn_dwell_s'] != primary['pre_turn_dwell_s']
                             and changed['tracks_sha256'] != primary['tracks_sha256'],
            }[candidate]
            if not distinct:
                raise ValueError('Fallback has no distinct engineered change: '+case+'/'+candidate)
    for a,b in (('reference','contrast'),('divided_reference','divided_opening')):
        for candidate in CANDIDATES:
            left,right=configs[(a,candidate)],configs[(b,candidate)]
            for key in ('assignment_id','assignment_sha256','ego_blueprint','frames','rate_hz',
                        'requested_approach_speed_mps','pre_turn_dwell_s','camera_policy'):
                if left.get(key)!=right.get(key):
                    raise ValueError('Comparison fixed condition changed: '+a+'/'+b+'/'+key)
            if left['requested_turn_center_x_m']==right['requested_turn_center_x_m']:
                raise ValueError('Comparison lacks distinct authored turn locations')
    result={'format':'c111662-current-independent-audit-v1','candidate_count':16,
            'positive_compatibility_count':16,'positive_saved_processing_count':16,
            'missing_source_negative_count':16,'comparison_pairs_checked':8,
            'frontage_constructions_checked':16,
            'scope':'unselected synthetic diagnostic; no physical or legal acceptance',
            'passed':True}
    (ROOT/'update015-current-independent-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
