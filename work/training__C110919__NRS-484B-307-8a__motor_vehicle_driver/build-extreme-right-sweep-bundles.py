"""Materialize exact lateral candidates with explicitly synthetic CPU diagnostics."""
import copy
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'extreme_right_sweep_cases'

def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2)+'\n')
def rows(text):return [json.loads(line) for line in text.splitlines() if line.strip()]
def lines(items):return ''.join(json.dumps(item,separators=(',',':'))+'\n' for item in items)

def displacement(center,offset):
    x,y=center
    if y<=-7:return offset,0
    if x>=7:return 0,-offset
    radius=math.hypot(7-x,-7-y)
    if not 4<radius<6:raise ValueError('Synthetic turn center outside authored arc')
    return (7-x)*offset/radius,(-7-y)*offset/radius

def diagnostic(base,offset):
    output=copy.deepcopy(base)
    files=output['files']
    native=rows(files['native_samples.jsonl'])
    trace=rows(files['trace.jsonl'])
    evidence=rows(files['capture/evidence.jsonl'])
    body_history=rows(files['body_history.jsonl'])
    if any(len(group)!=480 for group in (native,trace,evidence,body_history)):
        raise ValueError('Synthetic source frame count differs')
    for index,(sample,t,e,b) in enumerate(zip(native,trace,evidence,body_history)):
        dx,dy=displacement(sample['native_center_xy_m'],offset)
        sample['native_center_xy_m']=[sample['native_center_xy_m'][0]+dx,
                                     sample['native_center_xy_m'][1]+dy]
        sample['native_body_xy_m']=[[p[0]+dx,p[1]+dy] for p in sample['native_body_xy_m']]
        sample['lateral_right_offset_m']=offset
        sample['controller_request']['lateral_right_offset_m']=offset
        x,y=sample['native_center_xy_m']
        road=1 if y<=-7 else (2 if x>=7 else 13)
        sample['native_lane_geometry']={
            'road_id':road,'lane_id':-1,'lane_width_m':3.5,
            'lane_center_xy_m':[1.75,y] if road==1 else ([x,-1.75] if road==2 else [x,y]),
            'right_edge_xy_m':[3.5,y] if road==1 else ([x,-3.5] if road==2 else [x,y])}
        t['position']['x']+=dx;t['position']['y']+=dy
        t['position_m'][0]+=dx;t['position_m'][1]+=dy
        e['ego']['position_m'][0]+=dx;e['ego']['position_m'][1]+=dy
        for item in (e['ego']['body_vertices_m'],b['body_vertices_m']):
            for point in item:point[0]+=dx;point[1]+=dy
        if index==0 and max(p[0] for p in sample['native_body_xy_m'])>3.5:
            raise ValueError('Synthetic body exceeds authored right edge')
    files['native_samples.jsonl']=lines(native)
    files['trace.jsonl']=lines(trace)
    files['capture/evidence.jsonl']=lines(evidence)
    files['body_history.jsonl']=lines(body_history)
    geometry=json.loads(files['road_geometry.json'])
    geometry['approach_lateral_geometry']={
        'road_id':1,'lane_id':-1,'lane_center_x_m':1.75,
        'lane_width_m':3.5,'right_edge_x_m':3.5,
        'left_neighbor_lane_id':1,'left_neighbor_width_m':3.5,
        'highway_width_m':7.0}
    files['road_geometry.json']=json.dumps(geometry)+'\n'
    files['context.json']=json.dumps({'surveyed_right_turn':geometry})+'\n'
    capture=json.loads(files['capture/manifest.json'])
    capture['sources']['trace.jsonl']=hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()
    files['capture/manifest.json']=json.dumps(capture)+'\n'
    return output

def main():
    stage_path=HERE/'proposals/extreme-right-sweep-candidate.json'
    stage=read(stage_path)
    base_manifest=read(HERE/'update041-traffic-timing-sweep-manifest.json')
    base=next(c for c in base_manifest['cases'] if c['authored_traffic_launch_frame']==30)
    base_diag=read(HERE/'traffic_timing_sweep_cases'/base['case_id']/'diagnostic.json')
    by_candidate={'primary':{'construction':base['construction'],
        'construction_sha256':base['construction_sha256']},
        **{c['id']:c for c in base['candidates']}}
    cases=[c for c in stage['cases'] if c.get('sweep_id')=='C110919-extreme-right']
    if len(cases)!=5:raise ValueError('Exact lateral case set differs')
    result={'format':'c110919-extreme-right-sweep-exact-candidates-v1',
            'assignment_id':HERE.name,'stage_sha256':sha(stage_path),
            'runtime_manifest_sha256':sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json'),
            'status':'unselected_cpu_candidate','cases':[]}
    native=HERE/'native'
    for case in cases:
        ident=case['case_id'];offset=case['sweep_point']['lateral_right_offset_m']
        diag=diagnostic(base_diag,offset)
        diagnostic_path=OUT/ident/'diagnostic.json';save(diagnostic_path,diag)
        rel=str(diagnostic_path.relative_to(ROOT))
        recipe={'format':'worker-fixture-recipe',
                'sources':[{'path':'diagnostic-input.json','source':rel,'sha256':sha(diagnostic_path)}],
                'generator':{'source':rel,'sha256':sha(diagnostic_path)}}
        recipe_path=OUT/ident/'fixture-recipe.json';save(recipe_path,recipe)
        contract=copy.deepcopy(read(HERE/base['measurement_contract']))
        contract['case_id']=ident
        contract_path=OUT/ident/'measurement-contract.json';save(contract_path,contract)
        entry={'case_id':ident,'sweep_id':'C110919-extreme-right',
               'authored_lateral_right_offset_m':offset,
               'candidate_risk':{'status':'physical','reason':
                 'Original Native body/lane bounds, turn route and four-camera pixels require capture and independent review'},
               'fixture_recipe':str(recipe_path.relative_to(ROOT)),
               'measurement_contract':str(contract_path.relative_to(HERE)),
               'measurement_procedure':{'entrypoint':'finalize.py',
                   'output_schema':'c110919-saved-analysis-v1'},'candidates':[]}
        for name in ('primary','fallback1','fallback2','fallback3'):
            ref=by_candidate[name]
            path=HERE/ref['construction']
            if sha(path)!=ref['construction_sha256']:raise ValueError('Timing construction changed')
            package=copy.deepcopy(read(path))
            files={f['path']:f['content'] for f in package['files']}
            config=json.loads(files['config.json'])
            config.update({'case_id':ident,'selected_case_id':ident,'supported_case_ids':[ident],
                'sweep_id':'C110919-extreme-right','case_suffix':'extreme_right_sweep',
                'traffic_launch_frame':30,'lateral_right_offset_m':offset,
                'case':case,'recording_description':case['recording_description']})
            if 'native_lane_geometry' not in config['mandatory_channels']:
                config['mandatory_channels'].append('native_lane_geometry')
            files['config.json']=json.dumps(config,indent=2)+'\n'
            for target,source in (('runner.py','traffic_timing_sweep_runner.py'),
                                  ('finalize.py','traffic_timing_sweep_finalize.py'),
                                  ('extreme_right_sweep.py','extreme_right_sweep.py')):
                files[target]=(native/source).read_text()
            package.update({'case_id':ident,
                'files':[{'path':key,'content':value} for key,value in files.items()],
                'recording_description':case['recording_description'],
                'mechanisms':['Authored lateral route and spawn offset',
                    'Original Native lane/width and four-corner body capture',
                    'Four joined original source cameras'],
                'status':'unselected_cpu_candidate'})
            out=OUT/ident/name/'construction.json';save(out,package)
            item={'id':name,'construction':str(out.relative_to(HERE)),
                  'construction_sha256':sha(out)}
            if name=='primary':entry.update({k:item[k] for k in ('construction','construction_sha256')})
            else:
                item.update({'trigger':ref['trigger'],'changed_knobs':ref['changed_knobs']})
                entry['candidates'].append(item)
        result['cases'].append(entry)
    target=HERE/'update052-extreme-right-sweep-manifest.json';save(target,result)
    print(json.dumps({'exact_cases':len(cases),'candidate_bundles':4*len(cases),
                      'manifest_sha256':sha(target),'selected':False}))

if __name__=='__main__':main()
