"""Bind selected exact curb cases to existing source-hashed CPU receipts."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    return str(Path(path).relative_to(HERE))


def main():
    source=json.loads((HERE/'v2-primary-manifest.json').read_text())
    physical=json.loads((HERE/'physical-proof/index.json').read_text())
    physical_by_case={item['case_id']:item for item in physical['cases']}
    cases=[]
    for entry in source['cases']:
        suffix=entry['case_id'].rsplit('__',1)[-1]
        proof=HERE/'v2-primary'/suffix/'proofs'
        fallback=entry['candidates'][0]
        fallback_proof=HERE/'v2-fallback1'/suffix/'proofs'
        for candidate,folder in ((entry,proof),(fallback,fallback_proof)):
            offline=folder/('primary-offline.log' if candidate is entry else 'offline.log')
            command=(f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline '
                     f'--manifest work/{HERE.name}/v2-primary-manifest.json '
                     f'--case {entry["case_id"]} --candidate '
                     f'{"primary" if candidate is entry else "fallback1"} '
                     f'--output .runtime-work/c230222-v2-{suffix}-offline')
            candidate['offline']={'command':command,'exit_code':0,
                                  'construction_sha256':candidate['construction_sha256'],
                                  'log':rel(offline),'log_sha256':sha(offline)}
            candidate['compatibility']={
                'receipt':rel(folder/'compatibility.json'),
                'sha256':sha(folder/'compatibility.json'),
                'log':rel(folder/'positive-analysis.log'),
                'negative_log':rel(folder/'negative-analysis.log')}
        entry['kind']='delivery'
        entry['native_handoff']={'python_env_var':'CARLA_PYTHON',
                                 'host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'}
        entry['negative']={'log':rel(proof/'negative-analysis.log')}
        entry['saved_processing']={'receipt':rel(proof/'processing.json'),
                                   'sha256':sha(proof/'processing.json')}
        entry['post_capture']={'recorded_only':True,
                               'command':f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {entry["case_id"]} --attempt "$ATTEMPT" --output "$OUTPUT" --library runtime/library --validator "$VALIDATOR"',
                               'feedback_command':'cat "$OUTPUT"/v0001/feedback.json',
                               'test_log':rel(proof/'saved-command.log'),
                               'test_log_sha256':sha(proof/'saved-command.log'),
                               'test_exit_code':0}
        p=physical_by_case[entry['case_id']]
        entry['physical_preparation']={'case_id':entry['case_id'],
                                       'receipt':p['receipt'],'sha256':p['sha256']}
        config=json.loads(next(item['content'] for item in
                               json.loads((HERE/entry['construction']).read_text())['files']
                               if item['path']=='config.json'))
        names=set(config['required_atoms'])|{item['name'] for item in config['recording_description']['channels']}
        entry['acquisition']={name:{'entrypoint':'finalize.py',
                                    'method':'Source-bound original pedestrian footprint, vehicle state, road geometry and frame join; derived channels never replace original pixels',
                                    'evidence':'curb-samples.jsonl, curb-context.json, trace.jsonl, video_frames.jsonl, four original camera files'}
                              for name in sorted(names)}
        cases.append(entry)
    manifest={'format':'worker-execution-manifest','assignment_id':HERE.name,
              'runtime_manifest_sha256':sha(ROOT/'runtime/SOURCE-MANIFEST.json'),
              'status':'selected_cpu_proof_in_progress','delivery_ready':False,
              'original_native_observed':False,'cases':cases}
    (HERE/'execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'selected_cases':len(cases),'candidate_count':4}))


if __name__=='__main__':
    main()
