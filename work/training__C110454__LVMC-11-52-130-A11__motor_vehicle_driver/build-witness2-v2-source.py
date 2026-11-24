"""Create an unselected current-profile 600-frame source packet for witness 2."""
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DEST=ROOT/'.runtime-work/c110454-current-profile/saved-attempt-v6-witness_2'

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def main():
    fixture=load(HERE/'saved-fixture-proof.py','saved_fixture')
    probe=load(HERE/'probe-current-process-saved.py','current_probe')
    fixture.make_base(DEST,'witness_2',600,full_resolution=True)
    probe.enrich_current_graph_sources(DEST)
    for old,new in (('intersection','reference_corner'),('parking','driver_reference')):
        (DEST/(old+'.mkv')).rename(DEST/(new+'.mkv'))
    construction=json.loads((HERE/'draft-current-primaries/witness_2/construction.json').read_text())
    config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
    (DEST/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    print(json.dumps({'attempt':str(DEST),'frames':600,
                      'synthetic_diagnostic':True,'native_executed':False}))

if __name__=='__main__':main()
