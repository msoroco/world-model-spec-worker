"""Build exact mapped school-zone candidate and three physical-risk fallbacks."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

from u_turn_363_school import measure_school_candidate

HERE = Path(__file__).resolve().parent
PREFIX = HERE.name + '__'
CASE_ID = PREFIX + 'prohibition_363'
OLD_ID = PREFIX + 'prohibition_227'
SOURCE_PREFIX = 'work/' + HERE.name + '/'


def read(name):
    return json.loads((HERE/name).read_text())


def write(name, value, compact=False):
    path = HERE/name
    path.write_text(json.dumps(value, indent=None if compact else 2,
        separators=(',', ':') if compact else None, allow_nan=False)+'\n')
    return sha256(path.read_bytes()).hexdigest()


def diagnostic():
    source = read('diagnostic-prohibition_227.json')
    source['files'].pop('u_turn_227_divider.json')
    waypoint = SimpleNamespace(road_id=7, lane_id=-1,
        transform=SimpleNamespace(location=SimpleNamespace(x=0, y=0)))
    signs = [{'landmark_id':'school-zone-synthetic-0','road_id':7,
              'xy_m':[12, 1], 'name':'SCHOOL ZONE',
              'type':'synthetic', 'value':''}]
    packet = measure_school_candidate({'approach':waypoint}, signs)
    packet['source_landmarks'] = signs
    source['files']['u_turn_363_school.json'] = json.dumps(
        {'school_zone_candidate':packet}, indent=2)+'\n'
    source['files']['u_turn_fixture_provenance.json'] = json.dumps({
        'scope':'CPU diagnostic only; synthetic school landmark, actors and black video',
        'statutory_status':'official designation, children, hours, sign and beacon unknown',
        'template_source':SOURCE_PREFIX+'diagnostic-prohibition_227.json'}, indent=2)+'\n'
    digest = write('diagnostic-prohibition_363.json', source, compact=True)
    recipe = {'format':'worker-fixture-recipe',
        'sources':[{'path':'diagnostic-input.json',
                    'source':SOURCE_PREFIX+'diagnostic-prohibition_363.json',
                    'sha256':digest}],
        'generator':{'source':SOURCE_PREFIX+'diagnostic-prohibition_363.json',
                     'sha256':digest}}
    write('diagnostic-recipe-prohibition_363.json', recipe)


def contract():
    source = read('measurement-contract-safety_clear.json')
    source['case_id'] = CASE_ID
    source['requirements'].append({
        'disposition_index':4,
        'requirement':'Native mapped school-zone candidate and unresolved NRS 484B.363(3) exceptions',
        'source':'inputs/'+HERE.name+'/assignment.json',
        'output_key':'school_zone_candidate',
        'method':'measure_school_zone_candidate',
        'value_type':'object','kind':'sourced_context',
        'inputs':['u_turn_363_school.json','u_turn_context.json']})
    source['negative'] = {'remove':['u_turn_363_school.json'],
        'error_contains':'Missing required source: u_turn_363_school.json'}
    write('measurement-contract-prohibition_363.json', source)


def construction(candidate, description):
    suffix = '' if candidate == 'primary' else '-'+candidate
    source = read('construction-prohibition_227'+suffix+'.json')
    source['case_id'] = CASE_ID
    source['recording_description'] = deepcopy(description)
    source['measurement_plan']['original_sources'] = [
        'u_turn_363_school.json' if item == 'u_turn_227_divider.json' else item
        for item in source['measurement_plan']['original_sources']]
    source['static_checks'] = [
        'Native mapped school-zone sign candidate retained with statutory exception states unknown'
        if 'median gap' in item or 'divider' in item.lower() else item
        for item in source['static_checks']]
    source['mechanisms'].pop('median_divider', None)
    source['mechanisms']['school_zone'] = (
        'Native mapped school-zone landmark; official designation, children, '
        'school session, exempt periods, operational beacon and effective sign unknown')
    config_name = 'source-construction-prohibition_227'+suffix+'-config.json'
    config = read(config_name)
    config['selected_case_id'] = CASE_ID
    config['case']['case_id'] = CASE_ID
    config['case']['recording_description'] = deepcopy(description)
    config['supported_case_ids'] = [CASE_ID]
    write('source-construction-prohibition_363'+suffix+'-config.json', config)
    for item in source['files']:
        item['content'] = (json.dumps(config, indent=2)+'\n'
                           if item['path']=='config.json'
                           else (HERE/item['path']).read_text())
    name = 'construction-prohibition_363'+suffix+'.json'
    return name, write(name, source)


def main():
    manifest = read('execution-manifest.json')
    if any(entry['case_id']==CASE_ID for entry in manifest['cases']):
        raise ValueError('363 case already exists')
    description = deepcopy(read('construction-prohibition_227.json')['recording_description'])
    description['context_inputs'][-1] = {
        'name':'school_zone_candidate','unit':'structured context',
        'method':'Native school-zone landmark with statutory exception states unknown'}
    diagnostic()
    contract()
    variants = {candidate:construction(candidate,description)
        for candidate in ('primary','fallback1','fallback2','fallback3')}
    base = deepcopy(next(entry for entry in manifest['cases'] if entry['case_id']==OLD_ID))
    for key in ('offline','compatibility','negative','delivery_acceptance'):
        base.pop(key,None)
    base['case_id'] = CASE_ID
    base['construction'],base['construction_sha256'] = variants['primary']
    base['measurement_contract'] = 'measurement-contract-prohibition_363.json'
    base['fixture_recipe'] = SOURCE_PREFIX+'diagnostic-recipe-prohibition_363.json'
    base['candidate_risk']['reason'] = (
        'Mapped school sign or required statutory time/child/beacon sources may not '
        'materialize while U-turn and participants remain measurable')
    base['acquisition'].pop('divider_candidate',None)
    base['acquisition']['school_zone_candidate'] = {
        'entrypoint':'runner.py','method':'Native mapped school-zone landmark search',
        'evidence':'u_turn_363_school.json and u_turn_context.json'}
    base['post_capture']['command'] = base['post_capture']['command'].replace(OLD_ID,CASE_ID)
    for fallback in base['candidates']:
        ident = fallback['id']
        fallback['construction'],fallback['construction_sha256'] = variants[ident]
        for key in ('offline','compatibility'):
            fallback.pop(key,None)
    manifest['cases'].append(base)
    write('execution-manifest.json',manifest)
    print(CASE_ID, 'primary and three fallbacks built; proofs pending')


if __name__=='__main__':
    main()
