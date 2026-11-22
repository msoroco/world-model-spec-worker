"""Independent source audit of the same-site opposite left-turn CPU diagnostic."""
import argparse
import hashlib
import json
from pathlib import Path
from shapely.geometry import MultiPoint, Polygon


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit(root, crossing_source=None):
    root=Path(root)
    first=read(root/'construction.json')
    first_receipt=read(root/'primary-compat-receipt.json')
    if (first_receipt.get('passed') is not True or
        first_receipt.get('construction_sha256')!=sha_bytes((root/'construction.json').read_bytes())):
        raise ValueError('Reference other-first compatibility proof changed')
    first_files={f['path']:f['content'] for f in first['files']}
    first_site=json.loads(first_files['site.json'])
    first_fallback_proofs=[]
    for candidate in ('fallback1','fallback2','fallback3'):
        path=root/'cases/yield_sign_other_first'/(candidate+'-construction.json')
        variant=read(path)
        proof=read(root/('other-first-'+candidate+'-compat-receipt.json'))
        negative=root/('other-first-'+candidate+'-negative.log')
        if (proof.get('passed') is not True or len(proof.get('checks',[]))!=11 or
            proof.get('candidate_id')!=candidate or
            proof.get('construction_sha256')!=sha_bytes(path.read_bytes()) or
            proof.get('negative_log_sha256')!=sha_bytes(negative.read_bytes())):
            raise ValueError(candidate+': other-first exact positive/negative proof changed')
        files={f['path']:f['content'] for f in variant['files']}
        site=json.loads(files['site.json'])
        expected=json.loads(json.dumps(first_site))
        if candidate=='fallback1':expected['approaches']['ego']['spawn_pose']=[-5,0,0,0]
        elif candidate=='fallback2':
            expected['approaches']['other']['spawn_pose']=[15,-20,0,90]
            expected['approaches']['other']['route_xy_m'][0]=[15,-20]
        else:expected['camera_poses']['overview']=[5,-5,11,0,-25,0]
        if candidate in ('fallback1','fallback2'):
            site['source_documents']=expected['source_documents']
        if (site!=expected or variant['case_id']!=first['case_id'] or
            any(variant[k]!=first[k] for k in ('law_id','cell_id','actor'))):
            raise ValueError(candidate+': other-first fixed case/site or risk knob changed')
        first_fallback_proofs.append({'candidate_id':candidate,'construction_sha256':proof['construction_sha256']})
    additional_fallback_proofs={}
    for case, stem in (('yield_sign_ego_first','ego-first'),('yield_sign_other_inside','other-inside')):
        selected=read(root/'cases'/case/'construction.json')
        selected_files={f['path']:f['content'] for f in selected['files']}
        selected_site=json.loads(selected_files['site.json'])
        proofs=[]
        for candidate in ('fallback1','fallback2','fallback3'):
            path=root/'cases'/case/(candidate+'-construction.json')
            variant=read(path)
            proof=read(root/(stem+'-'+candidate+'-compat-receipt.json'))
            negative=root/(stem+'-'+candidate+'-negative.log')
            if (proof.get('passed') is not True or len(proof.get('checks',[]))!=11 or
                proof.get('candidate_id')!=candidate or
                proof.get('construction_sha256')!=sha_bytes(path.read_bytes()) or
                proof.get('negative_log_sha256')!=sha_bytes(negative.read_bytes())):
                raise ValueError(case+'/'+candidate+': exact positive/negative proof changed')
            files={f['path']:f['content'] for f in variant['files']}
            site=json.loads(files['site.json'])
            expected=json.loads(json.dumps(selected_site))
            if candidate=='fallback1':
                expected['approaches']['ego']['spawn_pose']=[-5,0,0,0]
                expected['approaches']['ego']['route_xy_m'][0]=[-5,0]
            elif candidate=='fallback2':
                expected['approaches']['other']['spawn_pose']=[15,-20,0,90]
                expected['approaches']['other']['route_xy_m'][0]=[15,-20]
            else:expected['camera_poses']['overview']=[5,-5,11,0,-25,0]
            if candidate in ('fallback1','fallback2'):
                site['source_documents']=expected['source_documents']
            if (site!=expected or variant['case_id']!=selected['case_id'] or
                any(variant[k]!=selected[k] for k in ('law_id','cell_id','actor'))):
                raise ValueError(case+'/'+candidate+': fixed case/site or risk knob changed')
            proofs.append({'candidate_id':candidate,'construction_sha256':proof['construction_sha256']})
        additional_fallback_proofs[case]=proofs
    directory=root/'cases/yield_sign_opposite_left'
    construction_path=directory/'construction.json'
    construction=read(construction_path)
    files={f['path']:f['content'] for f in construction['files']}
    config=json.loads(files['config.json'])
    site=json.loads(files['site.json'])
    receipt=read(root/'opposite-left-compat-receipt.json')
    fixture=read(directory/'diagnostic.json')
    if receipt.get('passed') is not True or len(receipt.get('checks',[]))!=11:
        raise ValueError('Exact compatibility proof missing')
    if receipt.get('construction_sha256')!=sha_bytes(construction_path.read_bytes()):
        raise ValueError('Construction differs from compatibility proof')
    if receipt.get('case_id')!=construction['case_id'] or config['selected_case_id']!=construction['case_id']:
        raise ValueError('Exact case identity changed')
    if any(construction[k]!=first[k] for k in ('law_id','cell_id','actor')):
        raise ValueError('Law, cell or actor changed')
    if (site['intersection_id']!=first_site['intersection_id'] or
        site['crossing_polygon_xy_m']!=first_site['crossing_polygon_xy_m'] or
        site['yield_sign']!=first_site['yield_sign'] or
        site['approaches']['ego']!=first_site['approaches']['ego']):
        raise ValueError('Junction, sign or ego approach changed')
    other=site['approaches']['other']
    if (site['approach_relation']!='opposite_directions' or
        other['highway_id']!=site['approaches']['ego']['highway_id'] or
        other['forward_xy']!=[-1,0] or
        other['route_xy_m']!=[[30,0],[15,0],[15,-15]]):
        raise ValueError('Opposite left-turn route missing')
    context_text=fixture['files']['junction_context.json']
    if receipt['fixture_manifest'].get('junction_context.json')!=sha_bytes(context_text.encode()):
        raise ValueError('Source context differs from proof')
    context=json.loads(context_text)
    if (context['approach_relation']!='opposite_directions' or
        context['turn_intent_source']!='controller_history.jsonl' or
        context['intersection_polygon_xy_m']!=site['crossing_polygon_xy_m']):
        raise ValueError('Opposite approach context differs')
    source=crossing_source or directory/'diagnostic.json'
    if crossing_source is None:
        crossing=fixture['files']['crossing_history.jsonl'].encode()
    else:
        crossing=Path(crossing_source).read_bytes()
    if receipt['fixture_manifest'].get('crossing_history.jsonl')!=sha_bytes(crossing):
        raise ValueError('Retained crossing source differs from compatibility proof')
    controls=fixture['files']['controller_history.jsonl'].encode()
    if receipt['fixture_manifest'].get('controller_history.jsonl')!=sha_bytes(controls):
        raise ValueError('Retained control source differs from compatibility proof')
    rows=[json.loads(s) for s in crossing.decode().splitlines() if s.strip()]
    commands=[json.loads(s) for s in controls.decode().splitlines() if s.strip()]
    if len(rows)!=60 or len(commands)!=60 or config['frames']!=900 or config['duration_s']!=45 or config['rate_hz']!=20:
        raise ValueError('Original diagnostic frame rate or selected duration changed')
    saved=read(root/'opposite-left-saved-receipt.json')
    if (saved.get('passed') is not True or saved.get('recorded_only') is not True or
        saved.get('case_id')!=construction['case_id'] or
        saved.get('analysis_revision',{}).get('construction_sha256')!=sha_bytes(construction_path.read_bytes()) or
        saved.get('timestamp_joins',{}).get('frames')!=900 or
        saved.get('originals_preserved') is not True):
        raise ValueError('Full-duration recorded-only source proof changed')
    polygon=Polygon(site['crossing_polygon_xy_m'])
    if not polygon.is_valid or polygon.area<=0:
        raise ValueError('Invalid crossing polygon')
    first_entry={'ego':None,'other':None}
    for i,(row,control) in enumerate(zip(rows,commands)):
        if row['frame']!=rows[0]['frame']+i or row['time_s']!=i/20 or control['frame']!=row['frame'] or control['time_s']!=row['time_s']:
            raise ValueError('Original frame/controller join changed')
        if row.get('other_left_turn_intended') is not True or control.get('other_left_turn_intended') is not True:
            raise ValueError('Other left-turn source intention missing')
        for role in ('ego','other'):
            actor=row[role]
            if actor['road_id']!=site['approaches'][role]['road_id'] or len(actor['body_vertices_xy_m'])<4:
                raise ValueError('Complete actor body/road identity missing')
            if first_entry[role] is None and MultiPoint(actor['body_vertices_xy_m']).convex_hull.intersects(polygon):
                first_entry[role]={'frame':row['frame'],'time_s':row['time_s']}
    if any(value is None for value in first_entry.values()):
        raise ValueError('Both complete bodies must enter crossing')
    measured=receipt.get('measurement_examples',{}).get('entry_timing',{}).get('value',{}).get('first_body_entry')
    if first_entry!=measured:
        raise ValueError('Independent entry timing differs from proof')
    expected_changes={
        'fallback1': ('approaches','ego','spawn_pose',[-5,0,0,0]),
        'fallback2': ('approaches','other','spawn_pose',[35,0,0,180]),
        'fallback3': ('camera_poses','overview',None,[5,-5,11,0,-25,0]),
    }
    fallback_proofs=[]
    for candidate, (_, role, key, wanted) in expected_changes.items():
        path=directory/(candidate+'-construction.json')
        variant=read(path)
        variant_files={f['path']:f['content'] for f in variant['files']}
        variant_site=json.loads(variant_files['site.json'])
        proof=read(root/('opposite-left-'+candidate+'-compat-receipt.json'))
        negative=root/('opposite-left-'+candidate+'-negative.log')
        if (proof.get('passed') is not True or len(proof.get('checks',[]))!=11 or
            proof.get('candidate_id')!=candidate or
            proof.get('construction_sha256')!=sha_bytes(path.read_bytes()) or
            proof.get('negative_log_sha256')!=sha_bytes(negative.read_bytes())):
            raise ValueError(candidate+': exact positive/negative compatibility proof changed')
        if variant['case_id']!=construction['case_id'] or variant_site['intersection_id']!=site['intersection_id'] or variant_site['crossing_polygon_xy_m']!=site['crossing_polygon_xy_m'] or variant_site['yield_sign']!=site['yield_sign']:
            raise ValueError(candidate+': fixed case/site condition changed')
        expected=json.loads(json.dumps(site))
        if key is None:expected['camera_poses'][role]=wanted
        else:expected['approaches'][role][key]=wanted
        observed=json.loads(json.dumps(variant_site))
        if candidate in ('fallback1','fallback2'):
            observed['source_documents']=expected['source_documents']
        if observed!=expected:
            raise ValueError(candidate+': unplanned site change')
        fallback_proofs.append({'candidate_id':candidate,'construction_sha256':proof['construction_sha256'],'risk_knob':candidate})
    return {'format':'worker-opposite-left-source-audit','passed':True,
            'case_id':construction['case_id'],'first_body_entry':first_entry,
            'same_junction_and_yield_sign':True,'opposite_approach':True,
            'other_left_turn_route_and_controller_intent':True,
            'other_first_fallback_proofs':first_fallback_proofs,
            'additional_fallback_proofs':additional_fallback_proofs,
            'fallback_proofs':fallback_proofs,
            'physical_acceptance_claimed':False,'legal_conclusion':'unresolved'}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--crossing-source',type=Path)
    args=parser.parse_args()
    print(json.dumps(audit(args.root,args.crossing_source),indent=2))
