"""Exact-case right-pass launcher; --check imports no CARLA.

The selected construction is materialized fresh by the pinned CPU runtime. An
operator supplies the CARLA Python and an exclusively owned server for capture.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

PACKAGE=Path(__file__).resolve().parent
REPO=PACKAGE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok,message):
    if not ok:
        raise ValueError(message)


def selected_manifest():
    canonical=PACKAGE/'execution-manifest.json'
    return canonical if canonical.is_file() else PACKAGE/'execution-manifest-unified-draft.json'


def check(manifest=None):
    path=Path(manifest) if manifest else selected_manifest()
    data=json.loads(path.read_text())
    require(data.get('assignment_id')==PACKAGE.name and
            data.get('format')=='worker-execution-manifest',
            'Wrong exact assignment manifest')
    cases=data.get('cases',[])
    require(len(cases)==2 and {e['case_id'] for e in cases}==
            {PACKAGE.name+'__reference',PACKAGE.name+'__contrast'},
            'Selected right-pass pair missing')
    proposal=json.loads((PACKAGE/'proposals/cases.json').read_text())
    source={c['case_id']:c for c in proposal['cases'] if c['target_type']!='baseline'}
    require(set(source)=={e['case_id'] for e in cases},'Canonical case coverage changed')
    for entry in cases:
        parts=[entry,*entry['candidates']]
        require(len(parts)==4 and {p.get('id') for p in entry['candidates']}==
                {'fallback1','fallback2','fallback3'},
                'Three exact fallback constructions required')
        for item in parts:
            construction=PACKAGE/item['construction']
            require(construction.is_file() and sha(construction)==item['construction_sha256'],
                    'Selected construction hash changed')
            payload=json.loads(construction.read_text())
            require(payload['case_id']==entry['case_id'] and
                    payload['recording_description']==source[entry['case_id']]['recording_description'],
                    'Selected capture contract differs')
            config=json.loads(next(f['content'] for f in payload['files'] if f['path']=='config.json'))
            require(config['case']==source[entry['case_id']] and
                    config['selected_case_id']==entry['case_id'],
                    'Selected case definition differs')
    return {'cases':len(cases),'fallbacks':sum(len(e['candidates']) for e in cases),
            'native_imported':False,'physical_acceptance_claimed':False}


def launch(case,candidate,output,python,host,port,manifest=None):
    manifest=Path(manifest) if manifest else selected_manifest()
    check(manifest)
    require(case in {PACKAGE.name+'__reference',PACKAGE.name+'__contrast'} and
            candidate in {'primary','fallback1','fallback2','fallback3'},
            'Unknown exact case or fallback')
    output=Path(output).resolve()
    require(not output.exists(),'Use a fresh output directory for an original attempt')
    subprocess.run([sys.executable,str(REPO/'runtime.py'),'materialize',
                    '--manifest',str(manifest),'--case',case,
                    '--candidate',candidate,'--output',str(output)],
                   cwd=REPO,check=True)
    subprocess.run([str(python),str(output/'runner.py'),'--output-dir',str(output),
                    '--host',str(host),'--port',str(port)],
                   cwd=output,check=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--check',action='store_true')
    p.add_argument('--manifest')
    p.add_argument('--case')
    p.add_argument('--candidate',default='primary')
    p.add_argument('--output-dir')
    p.add_argument('--python')
    p.add_argument('--host')
    p.add_argument('--port',type=int)
    args=p.parse_args()
    if args.check:
        print(json.dumps(check(args.manifest),sort_keys=True))
    else:
        require(all(x is not None for x in (args.case,args.output_dir,args.python,args.host,args.port)),
                'Original capture requires case, output, CARLA Python, host and port')
        launch(args.case,args.candidate,args.output_dir,args.python,args.host,args.port,args.manifest)
