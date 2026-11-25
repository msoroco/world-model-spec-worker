"""Create distinct no-line crosswalk and no-line/no-crosswalk view-point CPU cases."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASE = HERE.name
spec = importlib.util.spec_from_file_location('precedence_builder', HERE/'build-precedence.py')
precedence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(precedence)
SPECS = {
    'crosswalk_stop': ('crosswalk', -23.0, -32.0, 220),
    'crosswalk_no_stop': ('crosswalk', -23.0, -32.0, 0),
    'visible_point_stop': ('visible_point', -21.0, -30.0, 220),
    'visible_point_no_stop': ('visible_point', -21.0, -30.0, 0),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True)+'\n')


def road_variant(kind):
    root = ET.parse(HERE/'selected-road.xodr').getroot()
    for rid in ('250', '253'):
        road = next(r for r in root.findall('road') if r.get('id') == rid)
        objects = road.find('objects')
        for obj in list(objects):
            if obj.get('type') == 'roadMark' or kind == 'visible_point':
                objects.remove(obj)
        types = [o.get('type') for o in objects]
        if types != (['crosswalk'] if kind == 'crosswalk' else []):
            raise ValueError('Stop-reference removal differs')
    return ET.tostring(root, encoding='unicode')+'\n'


def request_rows(kind, reference, start, release):
    result = []
    for i in range(600):
        row = precedence.request(i, release)
        center = start + .05*min(i, 130) + .1*max(0, i-release)
        row['ego_center_xy_m'] = [round(center, 6), -1.75]
        row['ego_front_x_m'] = round(center+2, 6)
        row['marked_stop_line_x_m'] = None
        row['near_side_crosswalk_x_m'] = -23.0 if kind == 'crosswalk' else None
        row['governing_reference_x_m'] = reference
        row['governing_reference_kind'] = kind
        row['view_opening_physically_verified'] = False
        result.append(row)
    return result


def altered_sources(suffix, kind, reference, rows, road):
    recipe = precedence.sources(suffix, rows)
    root = HERE/'precedence'/suffix/'sources'
    (root/'road.xodr').write_text(road)
    context = json.loads((root/'signal-context.json').read_text())
    context.update(marked_stop_line_x_m=None,
                   near_side_crosswalk_x_m=-23 if kind == 'crosswalk' else None,
                   governing_reference_x_m=reference,
                   governing_reference_kind=kind,
                   view_opening_physically_verified=False)
    write(root/'signal-context.json', context)
    capture = json.loads((root/'capture/manifest.json').read_text())
    capture['sources']['road.xodr'] = sha(root/'road.xodr')
    write(root/'capture/manifest.json', capture)
    recipe_data = json.loads(recipe.read_text())
    for item in recipe_data['sources']:
        item['sha256'] = sha(REPO/item['source'])
    write(recipe, recipe_data)
    return recipe


def replace_exact(content, before, after):
    if before not in content:
        raise ValueError('Source transformation anchor missing: '+before[:75])
    return content.replace(before, after)


def construction(suffix, kind, reference, rows, road, candidate, shift):
    template = json.loads((HERE/'selected-candidates/controlled_1/primary/construction.json').read_text())
    item = copy.deepcopy(template)
    case = BASE+'__'+suffix
    item['case_id'] = case
    for file in item['files']:
        name = file['path'];content = file['content']
        if name == 'road.xodr':
            content = road
        elif name == 'request.jsonl':
            content = ''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows)
        elif name == 'config.json':
            cfg = json.loads(content)
            cfg.update(case_id=case,case={'case_id':case},supported_case_ids=[case],
                       candidate_id=candidate,spawn_shift_m=shift)
            content = json.dumps(cfg,indent=2,sort_keys=True)+'\n'
        elif name == 'runner.py':
            start=content.index('    for rid in (\'250\',\'253\'):')
            end=content.index('    rows=[json.loads', start)
            body = "    for rid in ('250','253'):\n        road=next(x for x in root.findall('road') if x.get('id')==rid)\n        types=[o.get('type') for o in road.findall('./objects/object')]\n        assert types=="+repr(['crosswalk'] if kind=='crosswalk' else [])+"\n        assert road.find('./lanes/laneSection/right/lane').get('id')=='-1'\n"
            content=content[:start]+body+content[end:]
            content=replace_exact(content,"        assert row['marked_stop_line_x_m']==-26 and row['near_side_crosswalk_x_m']==-23",
                                  f"        assert row['marked_stop_line_x_m'] is None and row['governing_reference_x_m']=={reference}")
            start=content.index("    if cfg['case_id'].endswith('controlled_1'):")
            end=content.index('    return {',start)
            body=(f"    assert any(rows[i]['ego_center_xy_m']==rows[i-1]['ego_center_xy_m'] and rows[i]['ego_front_x_m'] < {reference} for i in range(1,600))\n"
                  if not suffix.endswith('_no_stop') else
                  f"    assert not any(rows[i]['ego_center_xy_m']==rows[i-1]['ego_center_xy_m'] and rows[i]['ego_front_x_m'] < {reference} for i in range(1,600))\n")
            content=content[:start]+body+content[end:]
        elif name == 'native_signal.py':
            start=content.index('def map_check(path):')
            end=content.index('\ndef readback(',start)
            types=['crosswalk'] if kind=='crosswalk' else []
            body=f'''def map_check(path):
    path=Path(path);root=ET.parse(path).getroot();found={{}}
    for road_id,signal_id in ((250,'701'),(253,'702')):
        road=next((x for x in root.findall('road') if x.get('id')==str(road_id)),None)
        if road is None or road.get('junction')!='-1':raise ValueError('Original incoming road missing')
        signal=road.find('./signals/signal')
        objects=road.findall('./objects/object')
        if (signal is None or signal.get('id')!=signal_id or signal.get('type')!='1000001' or
                signal.get('dynamic')!='yes' or [o.get('type') for o in objects]!={types!r}):
            raise ValueError('Original signal or stop-reference geometry differs')
        found[str(road_id)]={{'signal_id':signal_id,'reference_kind':'{kind}','reference_s_m':{reference+60}}}
    return {{'map_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'incoming':found}}

'''
            content=content[:start]+body+content[end:]
        elif name == 'capture_selected.py':
            content=replace_exact(content,
                '"incoming":{"250":{"line_x_m":-26.0},"253":{"line_y_m":-26.0}},',
                f'"incoming":{{"250":{{"reference_x_m":{reference}}},"253":{{"reference_y_m":{reference}}}}},')
        elif name == 'original_measure.py':
            content=content.replace('LINE_X = -26.0',f'LINE_X = {reference}')
            content=content.replace("{'250': {'line_x_m': LINE_X},\n                                       '253': {'line_y_m': LINE_X}}",
                                    "{'250': {'reference_x_m': LINE_X},\n                                       '253': {'reference_y_m': LINE_X}}")
            content=content.replace('marked-line readback','governing-reference readback')
            content=content.replace('pre_line_low_speed_frames','pre_reference_low_speed_frames')
            content=content.replace('other_pre_line_low_speed_first_frame','other_pre_reference_low_speed_first_frame')
        elif name == 'original_finalize.py':
            content=content.replace('pre_line_low_speed_frames','pre_reference_low_speed_frames')
            content=content.replace('before marked line',f'before {kind} reference')
        elif name == 'finalize.py':
            content=content.replace(BASE+'__controlled_1',case)
            content=content.replace("context.get('marked_stop_line_x_m') != -26",
                                    "context.get('marked_stop_line_x_m') is not None or\n            context.get('governing_reference_x_m') != "+str(reference))
            content=content.replace("row['marked_stop_line_x_m'] != -26",
                                    "row['marked_stop_line_x_m'] is not None or\n                row['governing_reference_x_m'] != "+str(reference))
            content=content.replace('row[\'ego_front_x_m\'] < -26',f"row['ego_front_x_m'] < {reference}")
            content=content.replace('row[\'ego_front_x_m\'] >= -26',f"row['ego_front_x_m'] >= {reference}")
            content=content.replace('first_stop_line_cross_frame','first_reference_cross_frame')
            content=content.replace('pre_line_stationary_frames','pre_reference_stationary_frames')
            content=content.replace('marked stop line',kind+' reference')
            content=content.replace("'inoperative_signal_stop_measurement'", "'inoperative_signal_reference_measurement'")
            if suffix.endswith('_no_stop'):
                content=replace_exact(content,"'requested':True,'measured':metric['pre_reference_stationary_frames']>0,",
                                      "'requested':False,'measured':metric['pre_reference_stationary_frames']>0,")
                content=replace_exact(content,"'matched':metric['pre_reference_stationary_frames']>0,",
                                      "'matched':metric['pre_reference_stationary_frames']==0,")
        file['content']=content
    path=HERE/'precedence'/suffix/candidate/'construction.json'
    write(path,item)
    return path


def main():
    manifest=json.loads((HERE/'precedence-construction-manifest.json').read_text())
    proposal=json.loads((HERE/'proposals/cases.json').read_text())
    proposal['cases']=[c for c in proposal['cases'] if c['case_id'].rsplit('__',1)[-1] not in SPECS]
    for suffix,(kind,reference,start,release) in SPECS.items():
        case=BASE+'__'+suffix
        if any(e['case_id']==case for e in manifest['cases']):raise ValueError('Duplicate case')
        rows=request_rows(kind,reference,start,release)
        road=road_variant(kind)
        recipe=altered_sources(suffix,kind,reference,rows,road)
        values=[]
        for candidate,shift in (('primary',0),('fallback1',2.0)):
            path=construction(suffix,kind,reference,rows,road,candidate,shift)
            values.append((candidate,path.relative_to(HERE).as_posix(),sha(path)))
        contract=f'precedence/{suffix}/measurement-contract.json'
        write(HERE/contract,{'format':'worker-measurement-contract','case_id':case,
            'requirements':[{'disposition_index':1 if kind=='crosswalk' else 2,
                'requirement':'NRS-484B-250-4','source':'NRS 484B.250(4)',
                'output_key':'inoperative_signal_reference_measurement',
                'method':'measure_stop','value_type':'object','kind':'measured',
                'inputs':['vehicle-history.jsonl','signal-context.json','video_frames.jsonl',
                          'trace.jsonl','capture/evidence.jsonl']}],
            'negative':{'remove':['vehicle-history.jsonl'],
                        'error_contains':'Missing required source: vehicle-history.jsonl'},
            'status':'unselected_contract_draft'})
        entry={'case_id':case,'id':suffix,'kind':'draft_not_selected',
            'construction':values[0][1],'construction_sha256':values[0][2],
            'fixture_recipe':str(recipe.relative_to(REPO)),
            'measurement_contract':contract,'measurement_procedure':{'entrypoint':'finalize.py'},
            'candidate_risk':{'status':'physical','reason':'Native spawn clearance at the incoming lane may differ'},
            'candidates':[{'id':'fallback1','construction':values[1][1],
                'construction_sha256':values[1][2],
                'changed_knobs':['spawn_shift_m: 0 to 2.0'],
                'trigger':{'source':'native-map-readback.json and capture report',
                    'metric':'ego approach spawn clearance',
                    'failure_condition':'Primary spawn obstructed or outside lane'}}]}
        manifest['cases'].append(entry)
        source=next(c for c in proposal['cases'] if c['case_id']==BASE+'__controlled_1')
        item=copy.deepcopy(source);item['case_id']=case
        item['rationale']=f'Diagnostic {kind} stop-reference source branch; original Native physical view and stop remain unverified.'
        proposal['cases'].append(item)
    manifest['status']='selected_cpu_stop_reference_construction_in_progress'
    write(HERE/'stop-reference-construction-manifest.json',manifest)
    write(HERE/'proposals/cases.json',proposal)


if __name__=='__main__':main()
