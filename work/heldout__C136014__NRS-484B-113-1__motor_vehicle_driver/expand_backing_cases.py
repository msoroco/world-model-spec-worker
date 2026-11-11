"""Expand the two fixed-cell C136014 comparison cases into exact inline bundles."""
from __future__ import annotations
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parent
ASSIGNMENT=ROOT.name
PRIMARY=ASSIGNMENT+'__reverse_clear_traffic_steady'
CASES=('reverse_close_traffic_steady','reverse_clear_traffic_brakes')
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
primary=json.loads((ROOT/'construction.json').read_text())
primary_cfg=json.loads((ROOT/'config.json').read_text())
primary_spec=json.loads((ROOT/'diagnostic.json').read_text())
plan=json.loads((ROOT/'case-plan.json').read_text())
plan['requirement_dispositions'][0]['case_ids']=[c['case_id'] for c in plan['cases']]
(ROOT/'case-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
proposal=json.loads((ROOT/'proposals/cases.json').read_text())
if len(proposal['cases'])!=1:raise ValueError('Expected one primary proposal before exact expansion')
manifest=json.loads((ROOT/'execution-manifest.json').read_text())
if len(manifest['cases'])!=1:raise ValueError('Expected one primary manifest before exact expansion')

for slug in CASES:
    ident=ASSIGNMENT+'__'+slug
    folder=ROOT/'cases'/slug;folder.mkdir(parents=True,exist_ok=True)
    cfg=json.loads(json.dumps(primary_cfg));cfg['selected_case_id']=ident;cfg['case']['case_id']=ident
    (folder/'config.json').write_text(json.dumps(cfg,indent=2)+'\n')
    runner=(ROOT/'runner.py').read_text().replace(PRIMARY.split(ASSIGNMENT)[-1], '__'+slug)
    finalizer=(ROOT/'backing_finalizer.py').read_text().replace(PRIMARY.split(ASSIGNMENT)[-1], '__'+slug)
    test_runner=(ROOT/'tests/test_runner.py').read_text()
    if slug=='reverse_close_traffic_steady':
        runner=runner.replace('waypoint.previous(18.0)','waypoint.previous(10.0)')
        test_runner=test_runner.replace("self.assertEqual(scene['other'].transform.location.x,-18)","self.assertEqual(scene['other'].transform.location.x,-10)")
    else:
        runner=runner.replace("other.apply_control(carla.VehicleControl(throttle=.16,steer=0))",
               "other.apply_control(carla.VehicleControl(throttle=.16,steer=0) if len(frames)<80 else carla.VehicleControl(brake=.4,steer=0))")
    (folder/'runner.py').write_text(runner)
    (folder/'backing_finalizer.py').write_text(finalizer)
    (folder/'test_runner.py').write_text(test_runner)
    construction=json.loads(json.dumps(primary));construction['case_id']=ident
    for item in construction['files']:
        path=item['path']
        if path=='runner.py':source=folder/'runner.py'
        elif path=='backing_finalizer.py':source=folder/'backing_finalizer.py'
        elif path=='config.json':source=folder/'config.json'
        elif path=='tests/test_runner.py':source=folder/'test_runner.py'
        else:source=ROOT/path
        item['source']=str(source)
        item['content']=source.read_text()
    (folder/'construction.json').write_text(json.dumps(construction,indent=2)+'\n')
    contract=json.loads((ROOT/'first-measurement-contract.json').read_text());contract['case_id']=ident
    (folder/'measurement-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
    spec=json.loads(json.dumps(primary_spec))
    history=[json.loads(line) for line in spec['files']['backing_history.jsonl'].splitlines() if line]
    if slug=='reverse_close_traffic_steady':
        for row in history:
            other=row['other'];other['position_m'][0]+=5
            for vertex in other['body_vertices_m']:vertex[0]+=5
    else:
        for i,row in enumerate(history):
            other=row['other'];other['speed_mps']=max(.2,1-i*.1)
            shift=-.2*i
            other['position_m'][0]+=shift
            for vertex in other['body_vertices_m']:vertex[0]+=shift
    spec['files']['backing_history.jsonl']=''.join(json.dumps(row,separators=(',',':'))+'\n' for row in history)
    (folder/'diagnostic.json').write_text(json.dumps(spec,separators=(',',':'))+'\n')
    digest=sha(folder/'diagnostic.json')
    recipe={'format':'worker-fixture-recipe','sources':[{'path':'diagnostic-input.json','source':str(folder/'diagnostic.json'),'sha256':digest}],
            'generator':{'source':str(folder/'diagnostic.json'),'sha256':digest}}
    (folder/'diagnostic-recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
    case=json.loads(json.dumps(proposal['cases'][0]));case['case_id']=ident
    case['rationale']='Measure original backing with '+('closer approaching traffic' if slug=='reverse_close_traffic_steady' else 'approaching traffic braking')
    case['variable_assignments']['other_traffic_variant']={'kind':'world_setup','value':'close' if slug=='reverse_close_traffic_steady' else 'brakes'}
    case['paired_probe_id']='traffic_clearance' if slug=='reverse_close_traffic_steady' else 'traffic_interference'
    case['deliberate_differences']=['other traffic spacing'] if slug=='reverse_close_traffic_steady' else ['other traffic speed response']
    proposal['cases'].append(case)
    entry={'case_id':ident,'kind':'delivery','construction':f'cases/{slug}/construction.json','construction_sha256':sha(folder/'construction.json'),
           'candidate_risk':{'status':'physical','reason':'Native reverse encounter route and camera coverage may fail'},'candidates':[],
           'measurement_contract':f'cases/{slug}/measurement-contract.json',
           'measurement_procedure':{'entrypoint':'backing_finalizer.py'},
           'fixture_recipe':str(folder/'diagnostic-recipe.json'),
           'native_handoff':{'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'}}
    manifest['cases'].append(entry)
(ROOT/'proposals/cases.json').write_text(json.dumps(proposal,indent=2)+'\n')
(ROOT/'execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
