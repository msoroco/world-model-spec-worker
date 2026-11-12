"""Build exact two-direction 500-foot curve/crest diagnostic case."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

from sight_boundary_protocol import source as boundary_source
from u_turn_407_geometry import inspect_407_geometry

HERE=Path(__file__).resolve().parent
PREFIX=HERE.name+'__'
CASE_ID=PREFIX+'prohibition_407'
OLD_ID=PREFIX+'prohibition_363'
SOURCE_PREFIX='work/'+HERE.name+'/'


def read(name):return json.loads((HERE/name).read_text())
def write(name,value,compact=False):
    path=HERE/name
    path.write_text(json.dumps(value,indent=None if compact else 2,
        separators=(',',':') if compact else None,allow_nan=False)+'\n')
    return sha256(path.read_bytes()).hexdigest()


class Waypoint:
    lane_type='Driving'
    road_id=7
    def __init__(self,lane_id,index):
        self.lane_id,self.index=lane_id,index
        x=(-10.0 if lane_id<0 else 10.0)*index
        y=(3.0 if lane_id<0 else -3.0)+(index/23.0)**2*45.0
        z=1.5*max(0.0,1.0-abs(index-8)/8)
        self.transform=SimpleNamespace(location=SimpleNamespace(x=x,y=y,z=z))
    def previous(self,distance):
        if distance!=10.0:raise ValueError('Unexpected geometry sample')
        return [Waypoint(self.lane_id,self.index+1)]


def diagnostic():
    source=read('diagnostic-prohibition_363.json')
    source['files'].pop('u_turn_363_school.json')
    geometry=inspect_407_geometry({'approach':Waypoint(-1,0),
                                   'opposite':Waypoint(1,0)})
    source['files']['u_turn_407_geometry.json']=json.dumps(geometry,indent=2)+'\n'
    rows=[]
    for index,line in enumerate(source['files']['capture/evidence.jsonl'].splitlines()):
        row=json.loads(line)
        packet=boundary_source((152.0,152.4,152.8)[index%3])
        packet['method']='actual_actor_body_raycast_v2'
        row['visibility']=packet
        rows.append(json.dumps(row,allow_nan=False))
    source['files']['capture/evidence.jsonl']='\n'.join(rows)+'\n'
    source['files']['u_turn_fixture_provenance.json']=json.dumps({
        'scope':'CPU diagnostic only; synthetic curve/crest route and below/at/above 500 ft body-ray packet',
        'statutory_status':'physical obstruction and legal visibility not established',
        'template_source':SOURCE_PREFIX+'diagnostic-prohibition_363.json'},indent=2)+'\n'
    digest=write('diagnostic-prohibition_407.json',source,compact=True)
    write('diagnostic-recipe-prohibition_407.json',{
        'format':'worker-fixture-recipe',
        'sources':[{'path':'diagnostic-input.json',
                    'source':SOURCE_PREFIX+'diagnostic-prohibition_407.json',
                    'sha256':digest}],
        'generator':{'source':SOURCE_PREFIX+'diagnostic-prohibition_407.json',
                     'sha256':digest}})


def contract():
    source=read('measurement-contract-safety_clear.json')
    source['case_id']=CASE_ID
    source['requirements'].extend([{
        'disposition_index':5,
        'requirement':'Both-direction Native curve/crest site geometry and exact 152.4 m source probe for NRS 484B.407',
        'source':'inputs/'+HERE.name+'/assignment.json',
        'output_key':'curve_crest_geometry','method':'validate_geometry_packet',
        'value_type':'object','kind':'sourced_context',
        'inputs':['u_turn_407_geometry.json','u_turn_context.json']},{
        'disposition_index':6,
        'requirement':'Original nine-body-ray visibility in both incoming directions at 500 ft for NRS 484B.407',
        'source':'inputs/'+HERE.name+'/assignment.json',
        'output_key':'two_direction_500ft_visibility','method':'measure_407_visibility',
        'value_type':'object','kind':'sourced_context',
        'inputs':['capture/evidence.jsonl','u_turn_motion.jsonl','u_turn_context.json']}])
    source['negative']={'remove':['capture/evidence.jsonl'],
                        'error_contains':'Missing required source: capture/evidence.jsonl'}
    write('measurement-contract-prohibition_407.json',source)


def construction(candidate,description):
    suffix='' if candidate=='primary' else '-'+candidate
    source=read('construction-prohibition_363'+suffix+'.json')
    source['case_id']=CASE_ID
    source['recording_description']=deepcopy(description)
    source['measurement_plan']['original_sources']=[
        'u_turn_407_geometry.json' if item=='u_turn_363_school.json' else item
        for item in source['measurement_plan']['original_sources']]
    if 'capture/evidence.jsonl' not in source['measurement_plan']['original_sources']:
        source['measurement_plan']['original_sources'].append('capture/evidence.jsonl')
    source['static_checks']=[
        'Native curve/crest route and two-direction 500 ft body-ray sources retained'
        if 'school-zone' in item else item for item in source['static_checks']]
    source['mechanisms'].pop('school_zone',None)
    source['mechanisms']['curve_crest_sight']=(
        'Native curve/crest geometry, 230 m incoming routes and original 152.4 m nine-body-ray visibility; legal finding unresolved')
    config=read('source-construction-prohibition_363'+suffix+'-config.json')
    config['selected_case_id']=CASE_ID
    config['case']['case_id']=CASE_ID
    config['case']['recording_description']=deepcopy(description)
    config['supported_case_ids']=[CASE_ID]
    write('source-construction-prohibition_407'+suffix+'-config.json',config)
    for item in source['files']:
        item['content']=(json.dumps(config,indent=2)+'\n' if item['path']=='config.json'
                         else (HERE/item['path']).read_text())
    name='construction-prohibition_407'+suffix+'.json'
    return name,write(name,source)


def main():
    manifest=read('execution-manifest.json')
    if any(e['case_id']==CASE_ID for e in manifest['cases']):
        raise ValueError('407 case already exists')
    description=deepcopy(read('construction-prohibition_363.json')['recording_description'])
    description['context_inputs'][-1]={
        'name':'curve_crest_geometry','unit':'structured context',
        'method':'Native two-direction sampled curve/crest site geometry'}
    description['context_inputs'].append({
        'name':'two_direction_500ft_visibility','unit':'structured context',
        'method':'original 20 Hz nine-body-ray probe at 152.4 m on both incoming lanes'})
    diagnostic();contract()
    variants={c:construction(c,description) for c in
              ('primary','fallback1','fallback2','fallback3')}
    base=deepcopy(next(e for e in manifest['cases'] if e['case_id']==OLD_ID))
    for key in ('offline','compatibility','negative','delivery_acceptance'):
        base.pop(key,None)
    base['case_id']=CASE_ID
    base['construction'],base['construction_sha256']=variants['primary']
    base['measurement_contract']='measurement-contract-prohibition_407.json'
    base['fixture_recipe']=SOURCE_PREFIX+'diagnostic-recipe-prohibition_407.json'
    base['candidate_risk']['reason']=(
        'Native curve/crest may not block any body ray at 500 ft or complete the maneuver while original cameras remain measurable')
    base['acquisition'].pop('school_zone_candidate',None)
    base['acquisition']['curve_crest_geometry']={
        'entrypoint':'runner.py','method':'Native incoming waypoint geometry',
        'evidence':'u_turn_407_geometry.json and u_turn_context.json'}
    base['acquisition']['two_direction_500ft_visibility']={
        'entrypoint':'pipeline_capture.py','method':'actual_actor_body_raycast_v2',
        'evidence':'capture/evidence.jsonl and original motion'}
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
