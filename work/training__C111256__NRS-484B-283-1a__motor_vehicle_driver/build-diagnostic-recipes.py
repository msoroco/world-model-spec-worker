"""Build explicit, hash-bound synthetic sources for current public CPU checks."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
from geometry import open_drive

spec=importlib.util.spec_from_file_location('saved_fixture',HERE/'saved-fixture-proof.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,value):path.write_text(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n')
def lines(values):return ''.join(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n' for row in values)
def rows(path):return [json.loads(line) for line in path.read_text().splitlines() if line]

def build():
    manifest_path=HERE/'draft-execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    for case in ('witness_1','witness_2','exception_1_1','exception_1_2'):
        with tempfile.TemporaryDirectory(prefix='c111256-recipe-',dir=ROOT/'.runtime-work') as temporary:
            base=Path(temporary)/'base';fixture.make_attempt(base,case)
            evidence=rows(base/'capture/evidence.jsonl')
            mapping=rows(base/'video_frames.jsonl')
            frame_rows=[];graphs=[]
            for item,event in zip(mapping,evidence):
                frame=item['native_frame'];time=item['time_s']
                frame_rows.append({'frame':frame,'simulation_time':time,'time_s':time,
                    'base':f'graphs/base/{frame:08d}.pkl',
                    'abstract':f'graphs/abstract/{frame:08d}.pkl',
                    'synthetic_diagnostic':True})
                graphs.append({'path':f'capture/native/graphs/base/{frame:08d}.pkl',
                    'attributes':{'frame':frame,'simulation_time_s':time,
                        'synthetic_diagnostic':True,'source':'C111256 worker-authored crosswalk diagnostic'},
                    'nodes':[{'id':'ego','attributes':{'sem_class':'ego','entity_id':event['actor_id'],
                        'vertex':event['ego']['position_m'],'forward':[0.0,1.0,0.0],
                        'threedbbox':event['ego']['body_vertices_m']}}], 'edges':[]})
            files={str(p.relative_to(base)):p.read_text() for p in base.rglob('*')
                if p.is_file() and p.suffix not in ('.mkv','.pkl')
                and p.name!='config.json' and 'channels' not in p.parts}
            files['capture/native/frames.jsonl']=lines(frame_rows)
            files['road.xodr']=open_drive()
            cap=json.loads(files['capture/manifest.json'])
            cap['sources']={'road.xodr':hashlib.sha256(files['road.xodr'].encode()).hexdigest(),
                            'trace.jsonl':hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()}
            files['capture/manifest.json']=json.dumps(cap,separators=(',',':'))+'\n'
            cameras=json.loads((HERE/'draft-candidates'/case/'primary/construction.json').read_text())
            config=json.loads(next(f['content'] for f in cameras['files'] if f['path']=='config.json'))
            videos=[{'path':c['name']+'.mkv','frames':480,'width':c['width'],
                     'height':c['height'],'fps':20,'color':'black'} for c in config['cameras']]
            diagnostic=HERE/f'diagnostic-{case}.json'
            dump(diagnostic,{'files':files,'graphs':graphs,'videos':videos})
            source=HERE/'native/fixtures'/f'{case}-480.json'
            recipe=HERE/f'diagnostic-{case}-recipe.json'
            dump(recipe,{'format':'worker-fixture-recipe',
                'sources':[{'path':'diagnostic-input.json','source':str(source.relative_to(ROOT)),
                            'sha256':sha(source)}],
                'generator':{'source':str(diagnostic.relative_to(ROOT)),'sha256':sha(diagnostic)}})
            entry=next(e for e in manifest['cases'] if e['case_id']==HERE.name+'__'+case)
            entry['fixture_recipe']=str(recipe.relative_to(ROOT))
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    return len(manifest['cases'])

if __name__=='__main__':print('recipes',build())
