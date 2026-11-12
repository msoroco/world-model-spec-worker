"""Create the exact C230627 business-frontage candidate and three fallbacks."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from u_turn_403_3_frontage import measure_frontage

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREFIX = HERE.name + '__'
CASE_ID = PREFIX + 'prohibition_403_3'
SOURCE_PREFIX = 'work/' + HERE.name + '/'


def read(name):
    return json.loads((HERE/name).read_text())


def write(name, value):
    path = HERE/name
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    return sha256(path.read_bytes()).hexdigest()


def config_for(candidate, description):
    source = ('config.json' if candidate == 'primary' else
              'source-construction-safety_clear-'+candidate+'-config.json')
    config = read(source)
    config['selected_case_id'] = CASE_ID
    config['case']['case_id'] = CASE_ID
    config['case']['recording_description'] = deepcopy(description)
    config['supported_case_ids'] = [CASE_ID]
    return config


def construction_for(candidate, description):
    source = ('construction.json' if candidate == 'primary' else
              'construction-safety_clear-'+candidate+'.json')
    construction = read(source)
    construction['case_id'] = CASE_ID
    construction['recording_description'] = deepcopy(description)
    construction['measurement_plan']['original_sources'].append('u_turn_403_3_frontage.json')
    construction['static_checks'].append('Native built-frontage geometry, source use and nonjunction site retained')
    construction['mechanisms']['business_frontage'] = (
        'Native environment building boxes projected onto local 600 ft highway window; '
        'building use and statutory exceptions remain unresolved')
    config = config_for(candidate, description)
    config_name = ('source-construction-prohibition_403_3-config.json' if candidate == 'primary'
                   else 'source-construction-prohibition_403_3-'+candidate+'-config.json')
    write(config_name, config)
    for item in construction['files']:
        if item['path'] == 'config.json':
            item['content'] = json.dumps(config, indent=2)+'\n'
        else:
            item['content'] = (HERE/item['path']).read_text()
    name = ('construction-prohibition_403_3.json' if candidate == 'primary'
            else 'construction-prohibition_403_3-'+candidate+'.json')
    return name, write(name, construction)


def diagnostic():
    source = read('diagnostic-safety_clear.json')
    geometry = measure_frontage([
        {'source_id':'synthetic-building-1',
         'vertices_xy_m':[[-55,8],[55,8],[55,16],[-55,16]],
         'use_class':None,'use_source_ref':None}], (0,0),(1,0))
    geometry.update({'road_id':7,'approach_lane_id':-1,
                     'opposite_lane_id':1,'site_is_junction':False,
                     'candidate_index':0})
    source['files']['u_turn_403_3_frontage.json'] = json.dumps(
        {'built_frontage_candidate':geometry},indent=2)+'\n'
    source['files']['u_turn_fixture_provenance.json'] = json.dumps({
        'scope':'CPU diagnostic only; synthetic built frontage, actor motion and black video',
        'statutory_status':'unknown; building use and intersection/divided-opening alternatives unsourced',
        'template_source': SOURCE_PREFIX+'diagnostic-safety_clear.json'},indent=2)+'\n'
    path = HERE/'diagnostic-prohibition_403_3.json'
    path.write_text(json.dumps(source,separators=(',',':'),allow_nan=False)+'\n')
    digest = sha256(path.read_bytes()).hexdigest()
    recipe = {'format':'worker-fixture-recipe',
              'sources':[{'path':'diagnostic-input.json',
                          'source':SOURCE_PREFIX+'diagnostic-prohibition_403_3.json',
                          'sha256':digest}],
              'generator':{'source':SOURCE_PREFIX+'diagnostic-prohibition_403_3.json',
                           'sha256':digest}}
    write('diagnostic-recipe-prohibition_403_3.json',recipe)


def measurement_contract():
    contract = read('measurement-contract-safety_clear.json')
    contract['case_id'] = CASE_ID
    contract['requirements'].append({
        'disposition_index':2,
        'requirement':'Built frontage candidate for NRS 484B.403(3) and NRS 484B.010, with use and alternatives unresolved',
        'source':'inputs/'+HERE.name+'/assignment.json',
        'output_key':'built_frontage_candidate',
        'method':'measure_built_frontage',
        'value_type':'object','kind':'sourced_context',
        'inputs':['u_turn_403_3_frontage.json','u_turn_context.json']})
    contract['negative']={'remove':['u_turn_403_3_frontage.json'],
                          'error_contains':'Missing required source: u_turn_403_3_frontage.json'}
    write('measurement-contract-prohibition_403_3.json',contract)


def main():
    if any(entry['case_id']==CASE_ID for entry in read('execution-manifest.json')['cases']):
        raise ValueError('403(3) case already built; edit exact sources deliberately')
    description = deepcopy(read('construction.json')['recording_description'])
    description['context_inputs'].append({
        'name':'built_frontage_candidate','unit':'structured context',
        'method':'original Native building-box frontage in a 600 ft road window; use/exception status unresolved'})
    diagnostic()
    measurement_contract()
    variants = {candidate:construction_for(candidate,description)
                for candidate in ('primary','fallback1','fallback2','fallback3')}
    manifest = read('execution-manifest.json')
    base = deepcopy(manifest['cases'][0])
    for key in ('offline','compatibility','negative','delivery_acceptance'):
        base.pop(key,None)
    base['case_id'] = CASE_ID
    base['construction'],base['construction_sha256'] = variants['primary']
    base['fixture_recipe'] = SOURCE_PREFIX+'diagnostic-recipe-prohibition_403_3.json'
    base['measurement_contract'] = 'measurement-contract-prohibition_403_3.json'
    base['candidate_risk']['reason'] = 'Native built frontage may be insufficient, use unsourced, or U-turn/visibility may fail'
    base['acquisition']['built_frontage_candidate'] = {
        'entrypoint':'runner.py',
        'method':'Native building boxes projected onto local road tangent, with independent use unknown',
        'evidence':'u_turn_403_3_frontage.json and u_turn_context.json'}
    command = base['post_capture']['command']
    base['post_capture'] = {'recorded_only':True,
                            'command':command.replace(PREFIX+'safety_clear',CASE_ID),
                            'feedback_command':'cat "$PROCESSING_OUTPUT/feedback.json"'}
    for fallback in base['candidates']:
        candidate=fallback['id']
        fallback['construction'],fallback['construction_sha256']=variants[candidate]
        for key in ('offline','compatibility'):
            fallback.pop(key,None)
    manifest['cases'].append(base)
    write('execution-manifest.json',manifest)
    print(CASE_ID,'primary + 3 fallbacks constructed; exact proofs pending')


if __name__=='__main__':
    main()
