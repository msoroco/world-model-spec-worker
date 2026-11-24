"""Bind eighteen passing CPU constructions to six exact delivery cases."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PUBLIC=HERE/'current-public'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    m=json.loads((HERE/'current-execution-manifest.json').read_text())
    cproof={};oproof={}
    for branch in ('witness','exception','official'):
        for row in json.loads((PUBLIC/(branch+'-compat-summary.json')).read_text())['results']:
            cproof[(row['case'],row['candidate'])]=row
        for row in json.loads((PUBLIC/(branch+'-offline-summary.json')).read_text())['rows']:
            oproof[(row['case_id'].rsplit('__',1)[-1],row['candidate_id'])]=row
    sproof={(r['case'],r['candidate']):r for r in json.loads((PUBLIC/'all-selected-saved-summary.json').read_text())['results']}
    physical={x['case_id']:x for x in json.loads((HERE/'physical-proof/index.json').read_text())['cases']}
    for case in m['cases']:
        suffix=case['case_id'].rsplit('__',1)[-1]
        case['candidate_risk']['status']='physical'
        case['native_handoff']={'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'}
        case['physical_preparation']=physical[case['case_id']]
        construction=json.loads((HERE/case['construction']).read_text())
        config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
        names=set(config['required_atoms'])|{c['name'] for c in construction['recording_description']['channels']}
        case['acquisition']={name:{'entrypoint':'runner.py','evidence':'actor-frames.jsonl, video_frames.jsonl, trace.jsonl, capture/evidence.jsonl',
          'method':'original Native 20 Hz actor/frame join; current evidence is synthetic diagnostic'} for name in sorted(names)}
        for fallback in case['candidates']:
            trigger=fallback['trigger']
            trigger.setdefault('source',trigger.get('source_file','actor-frames.jsonl'))
            if suffix.startswith('exception'):
                trigger['failure_condition']='fewer than 80 source-bound synthetic officer visibility frames' if fallback['id']=='fallback1' else 'first requested direction frame after frame 60'
            else:
                trigger['failure_condition']='subject full-body clearance not before approach catchup' if fallback['id']=='fallback1' else 'approach catchup before last six seconds of capture'
        for item in [case]+case['candidates']:
            ident=item['id'];c=cproof[(suffix,ident)];o=oproof[(suffix,ident)];s=sproof[(suffix,ident)]
            if c['exit_code'] or o['exit_code'] or s['exit_code'] or c['construction_sha256']!=item['construction_sha256'] or o['construction_sha256']!=item['construction_sha256']:
                raise ValueError('Changed or failed selected proof: '+suffix+'/'+ident)
            item['offline']={'command':'.venv-cpu/bin/python runtime.py offline --manifest work/'+HERE.name+'/execution-manifest.json --case '+case['case_id']+' --candidate '+ident+' --output .runtime-work/c405647-1a-'+suffix+'-'+ident+'-offline-final --python .venv-cpu/bin/python',
              'exit_code':0,'construction_sha256':item['construction_sha256'],'log':o['log'],'log_sha256':o['log_sha256']}
            files=c['files']
            item['compatibility']={'receipt':files['compatibility.json']['path'],'sha256':files['compatibility.json']['sha256'],
              'log':files['analysis.log']['path'],'negative_log':files['negative.log']['path']}
            item['negative']={'log':files['negative.log']['path']}
            item['saved_processing']={'receipt':s['receipt'],'sha256':s['receipt_sha256']}
        primary=case['saved_processing']
        case['post_capture']={'recorded_only':True,
          'command':'.venv-cpu/bin/python runtime.py process-saved --manifest work/'+HERE.name+'/execution-manifest.json --case '+case['case_id']+' --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT" --library runtime/library --validator "$DECODER"',
          'feedback_command':'cat "$PROCESSED_OUT/v0001/feedback.json"','test_exit_code':0,
          'test_log':primary['receipt'],'test_log_sha256':primary['sha256']}
    m['format']='worker-execution-manifest';m['status']='delivery_prepared';m['delivery_ready']=False;m['original_native_observed']=False
    path=HERE/'execution-manifest.json';path.write_text(json.dumps(m,indent=2)+'\n')
    print(json.dumps({'cases':len(m['cases']),'candidates':sum(1+len(c['candidates']) for c in m['cases']),'manifest_sha256':sha(path)}))
if __name__=='__main__':main()
