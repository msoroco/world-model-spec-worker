"""Create exact mapped-divider U-turn candidate and three physical-risk fallbacks."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

from u_turn_227_divider import measure_divider_candidate

HERE=Path(__file__).resolve().parent
PREFIX=HERE.name+'__'
CASE_ID=PREFIX+'prohibition_227'
OLD_ID=PREFIX+'prohibition_403_3'
SOURCE_PREFIX='work/'+HERE.name+'/'


def read(name):return json.loads((HERE/name).read_text())
def write(name,value,compact=False):
    path=HERE/name
    path.write_text(json.dumps(value,indent=None if compact else 2,
                               separators=(',',':') if compact else None,
                               allow_nan=False)+'\n')
    return sha256(path.read_bytes()).hexdigest()


def lane(y,lane_id):
    transform=SimpleNamespace(location=SimpleNamespace(x=0,y=y),
                              get_forward_vector=lambda:SimpleNamespace(x=1,y=0))
    return SimpleNamespace(transform=transform,road_id=7,lane_id=lane_id,lane_width=3)


def diagnostic():
    source=read('diagnostic-prohibition_403_3.json')
    source['files'].pop('u_turn_403_3_frontage.json')
    scene={'approach':lane(0,-1),'opposite':lane(8,1)}
    box={'source_id':'GuardRail-synthetic-0','label':'GuardRail',
         'vertices_xy_m':[[-3,3.8],[3,3.8],[3,4.2],[-3,4.2]]}
    packet=measure_divider_candidate(scene,[box])
    source['files']['u_turn_227_divider.json']=json.dumps({'divider_candidate':packet},indent=2)+'\n'
    source['files']['u_turn_fixture_provenance.json']=json.dumps({
        'scope':'CPU diagnostic only; synthetic mapped divider, actor motion and black video',
        'statutory_status':'unknown; authority opening and actual physical crossing unverified',
        'template_source':SOURCE_PREFIX+'diagnostic-prohibition_403_3.json'},indent=2)+'\n'
    digest=write('diagnostic-prohibition_227.json',source,compact=True)
    recipe={'format':'worker-fixture-recipe',
            'sources':[{'path':'diagnostic-input.json',
                        'source':SOURCE_PREFIX+'diagnostic-prohibition_227.json',
                        'sha256':digest}],
            'generator':{'source':SOURCE_PREFIX+'diagnostic-prohibition_227.json',
                         'sha256':digest}}
    write('diagnostic-recipe-prohibition_227.json',recipe)


def contract():
    source=read('measurement-contract-safety_clear.json')
    source['case_id']=CASE_ID
    source['requirements'].append({
        'disposition_index':3,
        'requirement':'Mapped divided-highway space or barrier candidate for NRS 484B.227, with public-authority opening alternatives unresolved',
        'source':'inputs/'+HERE.name+'/assignment.json',
        'output_key':'divider_candidate','method':'measure_mapped_divider',
        'value_type':'object','kind':'sourced_context',
        'inputs':['u_turn_227_divider.json','u_turn_context.json']})
    source['negative']={'remove':['u_turn_227_divider.json'],
                        'error_contains':'Missing required source: u_turn_227_divider.json'}
    write('measurement-contract-prohibition_227.json',source)


def construction(candidate,description):
    suffix='' if candidate=='primary' else '-'+candidate
    old_name='construction-prohibition_403_3'+suffix+'.json'
    source=read(old_name)
    source['case_id']=CASE_ID
    source['recording_description']=deepcopy(description)
    original=source['measurement_plan']['original_sources']
    source['measurement_plan']['original_sources']=[
        'u_turn_227_divider.json' if item=='u_turn_403_3_frontage.json' else item
        for item in original]
    source['static_checks']=[
        'Mapped median gap and Native GuardRail/Wall/Fence source geometry retained'
        if 'built-frontage' in item else item for item in source['static_checks']]
    source['mechanisms'].pop('business_frontage',None)
    source['mechanisms']['median_divider']=(
        'Native opposing-lane edge gap and mapped barrier box; public-authority opening and crossing outcome unresolved')
    config_name='source-construction-prohibition_403_3'+suffix+'-config.json'
    config=read(config_name)
    config['selected_case_id']=CASE_ID
    config['case']['case_id']=CASE_ID
    config['case']['recording_description']=deepcopy(description)
    config['supported_case_ids']=[CASE_ID]
    new_config_name='source-construction-prohibition_227'+suffix+'-config.json'
    write(new_config_name,config)
    for item in source['files']:
        if item['path']=='config.json':item['content']=json.dumps(config,indent=2)+'\n'
        else:item['content']=(HERE/item['path']).read_text()
    name='construction-prohibition_227'+suffix+'.json'
    return name,write(name,source)


def main():
    manifest=read('execution-manifest.json')
    if any(entry['case_id']==CASE_ID for entry in manifest['cases']):
        raise ValueError('227 case already exists; edit exact sources deliberately')
    description=deepcopy(read('construction-prohibition_403_3.json')['recording_description'])
    description['context_inputs'][-1]={
        'name':'divider_candidate','unit':'structured context',
        'method':'original Native opposing-lane widths and mapped divider boxes; authority status unresolved'}
    diagnostic()
    contract()
    variants={c:construction(c,description) for c in
              ('primary','fallback1','fallback2','fallback3')}
    base=deepcopy(next(entry for entry in manifest['cases'] if entry['case_id']==OLD_ID))
    for key in ('offline','compatibility','negative','delivery_acceptance'):
        base.pop(key,None)
    base['case_id']=CASE_ID
    base['construction'],base['construction_sha256']=variants['primary']
    base['measurement_contract']='measurement-contract-prohibition_227.json'
    base['fixture_recipe']=SOURCE_PREFIX+'diagnostic-recipe-prohibition_227.json'
    base['candidate_risk']['reason']='Mapped median/barrier or crossing trajectory may not physically realize while cameras and traffic remain measurable'
    base['acquisition'].pop('built_frontage_candidate',None)
    base['acquisition']['divider_candidate']={
        'entrypoint':'runner.py',
        'method':'Native opposing-lane widths and mapped GuardRail/Wall/Fence boxes',
        'evidence':'u_turn_227_divider.json and u_turn_context.json'}
    base['post_capture']['command']=base['post_capture']['command'].replace(OLD_ID,CASE_ID)
    for fallback in base['candidates']:
        ident=fallback['id']
        fallback['construction'],fallback['construction_sha256']=variants[ident]
        for key in ('offline','compatibility'):
            fallback.pop(key,None)
    manifest['cases'].append(base)
    write('execution-manifest.json',manifest)
    print(CASE_ID,'primary and three fallbacks built; proofs pending')


if __name__=='__main__':main()
