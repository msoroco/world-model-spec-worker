"""Original Native C10389 delivery entrypoint; source request stays hash bound."""
import argparse
import hashlib
import json
from pathlib import Path
from capture import capture
from check import check
from source_observations import write as write_observations

HERE=Path(__file__).resolve().parent
SOURCES=('assignment-source.json','alley-stop.xodr','requested-tracks.jsonl')

def inspect():
    cfg=json.loads((HERE/'selected-config.json').read_text())
    for key,name in (('assignment_sha256','assignment-source.json'),('case_plan_sha256','selected-case-plan.json'),('road_sha256','alley-stop.xodr'),('tracks_sha256','requested-tracks.jsonl')):
        if cfg[key] != hashlib.sha256((HERE/name).read_bytes()).hexdigest():
            raise ValueError('Source request hash changed: '+name)
    if cfg['case_id'] not in json.loads((HERE/'config.json').read_text())['supported_case_ids']:
        raise ValueError('Selected case missing from delivery config')
    return {'source_request_checked':True,'original_native_observed':False,'case_id':cfg['case_id']}

def execute(output,host,port):
    inspect()
    output=Path(output).resolve()
    if not output.is_dir() or any(output.iterdir()):
        raise ValueError('Expected new empty executor output directory')
    bundle=output/'source-request';bundle.mkdir()
    for name in SOURCES:
        (bundle/name).write_bytes((HERE/name).read_bytes())
    (bundle/'config.json').write_bytes((HERE/'selected-config.json').read_bytes())
    (bundle/'case-plan.json').write_bytes((HERE/'selected-case-plan.json').read_bytes())
    check(bundle)
    capture(bundle,output/'native-attempt',host,port)
    write_observations(output/'native-attempt')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--output',type=Path,default=Path.cwd());parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args()
    if args.check:print(json.dumps(inspect()))
    else:execute(args.output,args.host,args.port)
