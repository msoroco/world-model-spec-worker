"""Bind the first exact caravan case to selected CPU measurement sources."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = 'training__C228508__NRS-484B-127-3__motor_vehicle_driver'
CASE = AID + '__probe_b'
CHANNELS = ('drv.following', 'rel.surface_gap', 'drv.queue_behind',
            'rel.same_direction', 'ru.trailer_or_combination',
            'drv.lane_change_feasible', 'kin.speed')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


description = {'channels': [
    {'name':name, 'unit':'structured', 'method':'original Native source rows joined by frame',
     'time_window':'all 600 original frames', 'reference_frame':'authored Native world',
     'uncertainty':'Synthetic fixture only until original Native source review',
     'sampling_rate_hz':20} for name in CHANNELS],
    'context_inputs':[],
    'limitations':['Static gap and entrant motion do not decide legal sufficiency or danger',
                   'Caravan membership, highway district and tow coupling require independent review']}
draft=json.loads((ROOT/'cases/probe_b/primary/construction.json').read_text())
entries=[]
for candidate in ('primary','fallback1'):
    proposal=json.loads((ROOT/'cases/probe_b'/candidate/'construction.json').read_text())
    config=json.loads(next(f['content'] for f in proposal['files'] if f['path']=='config.json'))
    config.update(gap_target_m=8, gap_tolerance_m=2)
    config['recording_description']=description
    files=[f for f in proposal['files'] if f['path'] not in ('config.json', 'finalize.py')]
    for item in files:
        if item['path']=='runner.py':
            item['content']=item['content'].replace('source-manifest.json','native-source-inventory.json')
    files += [{'path':'meter.py','source':str(ROOT/'native/finalize.py'),
               'content':(ROOT/'native/finalize.py').read_text().replace('source-manifest.json','native-source-inventory.json')},
              {'path':'finalize.py','source':str(ROOT/'native/selected_finalize.py'),
               'content':(ROOT/'native/selected_finalize.py').read_text()},
              {'path':'config.json','content':json.dumps(config,indent=2)+'\n'}]
    proposal['files']=files
    proposal['recording_description']=description
    proposal['status']='selected_cpu_package_in_progress'
    path=ROOT/'selected/probe_b'/candidate/'construction.json'
    write(path,proposal)
    entries.append({'id':candidate,'construction':str(path.relative_to(ROOT)),
                    'construction_sha256':sha(path)})
entry={'case_id':CASE,'kind':'delivery',
       'construction':entries[0]['construction'],
       'construction_sha256':entries[0]['construction_sha256'],
       'candidate_risk':{'status':'physical',
                         'reason':'Native group spacing and entrant lane transition may drift under velocity control'},
       'candidates':[{'id':'fallback1',
                     'construction':entries[1]['construction'],
                     'construction_sha256':entries[1]['construction_sha256'],
                     'trigger':{'source':'native_samples.jsonl',
                                'metric':'minimum original consecutive-body clearance',
                                'failure_condition':'Primary clearance or entrant transition misses its predeclared engineering target'},
                     'changed_knobs':['group speed 6 m/s to 5 m/s']}],
       'measurement_contract':'selected-probe_b-measurement-contract.json',
       'measurement_procedure':{'entrypoint':'finalize.py',
                                'output_schema':'worker-analysis-report'},
       'fixture_recipe':str((ROOT/'selected-probe_b-fixture-recipe.json').relative_to(ROOT.parents[1])),
       'delivery_readiness':'incomplete'}
manifest=json.loads((ROOT/'selected-execution-manifest.json').read_text())
manifest['cases']=[item for item in manifest['cases'] if item['case_id'] != CASE]+[entry]
path=ROOT/'selected-execution-manifest.json'
write(path,manifest)
print(json.dumps({'manifest_sha256':sha(path),'primary_sha256':entries[0]['construction_sha256'],
                  'fallback_sha256':entries[1]['construction_sha256']}))
