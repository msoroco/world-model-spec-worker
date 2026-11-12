"""CPU protocol fixtures for original station U-turn motion and Native closure."""
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/scenario_pipeline'))
from worker_exchange.native_output import assess_physical, default_descriptor
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, _closure

def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def put(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')
def config(entry):
    construction=json.loads((HERE/entry['construction']).read_text())
    return json.loads(next(item['content'] for item in construction['files'] if item['path']=='config.json'))

def prove(manifest):
    entries=manifest['cases'];cases=[e['case_id'] for e in entries]
    configs=[config(e) for e in entries]
    descriptors=[default_descriptor(c) for c in configs]
    if (len({json.dumps(d,sort_keys=True) for d in descriptors})!=1 or
            any((c.get('rate_hz'),c.get('frames'),c.get('duration_s'))!=(20,240,12) for c in configs)):
        raise ValueError('Station physical source descriptor is not shared across selected cases')
    descriptor=descriptors[0]
    if (descriptor.get('criterion'),descriptor.get('motion_source'),descriptor.get('body_key'),
            descriptor.get('heading_key'),descriptor.get('turn_degrees'))!=(
            'turn','participant_state.jsonl','ego.body_vertices_xy','ego.heading_deg',180):
        raise ValueError('Station physical descriptor does not assess original body/heading')
    cfg=configs[0];fixtures=[];summaries=[]
    station_context=(ROOT/'.runtime-work/c104538-front_of_entrance-primary-compat-v4/station_context.json').read_bytes()
    for kind in ('complete_motion','incomplete_motion','missing_evidence'):
        with tempfile.TemporaryDirectory(prefix='c104538-physical-',dir='/tmp') as temporary:
            root=Path(temporary)
            put(root/'config.json',cfg)
            (root/'station_context.json').write_bytes(station_context)
            mapping=[{'video_frame':i,'carla_frame':41000+i,'time_s':round(i/20,5)} for i in range(240)]
            (root/'video_frames.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in mapping))
            trace=[];participants=[]
            for i in range(240):
                t=round(i/20,5);x=5*i/239;degrees=(180 if kind=='complete_motion' else 90)*i/239
                trace.append({'frame':41000+i,'time_s':t,'position_m':[x,0,0],
                              'heading_deg':degrees})
                body=[[x-1,-.8],[x+1,-.8],[x+1,.8],[x-1,.8]]
                participants.append({'frame':41000+i,'time_s':t,
                                     'ego':{'actor_id':41,'center_xy':[x,0],
                                            'heading_deg':degrees,'body_vertices_xy':body,
                                            'lane_id':[7,1]}})
            (root/'trace.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in trace))
            if kind!='missing_evidence':
                (root/'participant_state.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in participants))
            assessed=assess_physical(root,cfg)
            expected={'complete_motion':'met','incomplete_motion':'not_met',
                      'missing_evidence':'unverified'}[kind]
            observed=assessed['physical_checks']['maneuver']['status']
            if observed!=expected:raise ValueError(f'Station motion fixture {kind}: {observed}, expected {expected}')
            result={'format':'worker-physical-source-protocol-fixture','fixture_kind':kind,
                    'diagnostic_fixture':True,'shared_cases':cases,
                    'provenance_kind':'native' if kind=='complete_motion' else 'diagnostic',
                    'provenance_scope':'emulated Native source structure; no real station or motion asserted',
                    'physical_acceptance_claimed':False,'legal_acceptance_claimed':False,
                    'physical_checks':assessed['physical_checks'],
                    'maneuver_completed':assessed['maneuver_completed'],
                    'realized_observables':assessed['realized_observables']}
            name='physical-'+kind+'.json';put(HERE/name,result)
            fixtures.append((kind,name,digest(HERE/name)))
            summaries.append(f'{kind}: {observed}; source-joined 240-frame original-body U-turn criterion; diagnostic only')
    with tempfile.TemporaryDirectory(prefix='c104538-lifecycle-',dir='/tmp') as temporary:
        attempt=Path(temporary);first=entries[0]
        (attempt/'construction.json').write_bytes((HERE/first['construction']).read_bytes())
        (attempt/'runner.py').write_bytes((HERE/'runner.py').read_bytes())
        seal={'events':['capture_finished','encoders_closed','restoration_verified'],
              'sources':{},'native_revision':{'construction_sha256':digest(attempt/'construction.json'),
              'runner_sha256':digest(attempt/'runner.py')}}
        put(attempt/'capture-seal.json',seal)
        try:acknowledge_owner_release(attempt,attempt/'owner-release.json',True)
        except ValueError as error:
            if 'has not exited' not in str(error):raise
        else:raise AssertionError('Premature station owner release accepted')
        record_native_exit(attempt)
        acknowledge_owner_release(attempt,attempt/'owner-release.json',True)
        _closure(attempt,attempt/'owner-release.json','native',False)
    events=seal['events']+['native_exit','owner_released','saved_processing_started']
    summaries.append('Lifecycle: '+' -> '.join(events)+'; premature owner release rejected')
    log_name='physical-source-protocol.log';(HERE/log_name).write_text('\n'.join(summaries)+'\n');log_sha=digest(HERE/log_name)
    for entry in entries:
        case=entry['case_id'];branch=case.rsplit('__',1)[-1]
        command=f'.venv-cpu/bin/python work/{HERE.name}/prove_physical_preparation.py --case {case}'
        proof={'format':'worker-physical-preparation-proof','case_id':case,
               'construction_sha256':entry['construction_sha256'],
               'fixture_scope':'shared original 20 Hz body/heading source protocol; diagnostic only',
               'fixtures':[{'kind':kind,'command':command,'exit_code':0,
                            'log':log_name,'log_sha256':log_sha,'result':name,
                            'result_sha256':checksum} for kind,name,checksum in fixtures],
               'lifecycle':{'events':events,'exit_code':0,'log':log_name,'log_sha256':log_sha}}
        name=branch+'-physical-preparation.json';put(HERE/name,proof)
        entry['physical_preparation']={'receipt':name,'sha256':digest(HERE/name)}
    (HERE/'execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return {'cases':len(entries),'fixtures':len(fixtures),'events':events}

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--case');args=parser.parse_args()
    manifest=json.loads((HERE/'execution-manifest.json').read_text())
    if args.case and args.case not in [e['case_id'] for e in manifest['cases']]:
        raise ValueError('Unknown C104538 case')
    print(json.dumps(prove(manifest)))

if __name__=='__main__':main()
