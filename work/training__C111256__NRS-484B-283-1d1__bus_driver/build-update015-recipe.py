"""Export two source-hashed 480-frame C111256 diagnostic fixture recipes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
NATIVE=HERE/'native'
CAMERAS=(('overview',1920,1080),('approach',1280,720),
         ('reference_corner',1280,720),('driver_reference',1280,720))
NAMES=('native_samples.jsonl','road_geometry.json','video_frames.jsonl',
       'body_history.jsonl','trace.jsonl','capture/evidence.jsonl',
       'capture/manifest.json','capture/native/frames.jsonl',
       'capture/recorder_info.txt','road.xodr')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]

def load_fixture():
    spec=importlib.util.spec_from_file_location('c111256_saved',HERE/'prove-saved-finalizer.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def build():
    fixture=load_fixture();sys.path.insert(0,str(NATIVE))
    from geometry import open_drive
    outputs=[]
    for suffix in ('reference','contrast'):
        with tempfile.TemporaryDirectory(dir=REPO/'.runtime-work',prefix='c111256-recipe-') as temp:
            attempt=fixture.make_attempt(Path(temp)/'attempt',suffix)
            traces=rows(attempt/'trace.jsonl')
            evidence=rows(attempt/'capture/evidence.jsonl')
            samples=rows(attempt/'native_samples.jsonl')
            if not len(traces)==len(evidence)==len(samples)==480:
                raise ValueError('Walk recipe raw source counts differ')
            graph_frames=[];graphs=[]
            for trace,ev,sample in zip(traces,evidence,samples):
                frame=trace['frame'];time=trace['time_s']
                x=trace['position']['x'];y=trace['position']['y']
                graph_frames.append({'frame':frame,'simulation_time':time,'time_s':time,
                    'base':f'graphs/base/{frame:08d}.pkl',
                    'abstract':f'graphs/abstract/{frame:08d}.pkl',
                    'synthetic_diagnostic':True})
                graphs.append({'path':f'capture/native/graphs/base/{frame:08d}.pkl',
                    'attributes':{'frame':frame,'simulation_time_s':time,
                                  'synthetic_diagnostic':True},
                    'nodes':[{'id':'ego','attributes':{'sem_class':'ego','entity_id':820,
                        'vertex':[x,y,.5],'forward':[0,1,0],
                        'threedbbox':ev['ego']['body_vertices_m']}}],
                    'edges':[]})
            (attempt/'capture/native').mkdir(parents=True,exist_ok=True)
            (attempt/'capture/native/frames.jsonl').write_text(''.join(
                json.dumps(row)+'\n' for row in graph_frames))
            (attempt/'road.xodr').write_text(open_drive())
            manifest=json.loads((attempt/'capture/manifest.json').read_text())
            manifest['sources']={'road.xodr':sha(attempt/'road.xodr'),
                                 'trace.jsonl':sha(attempt/'trace.jsonl')}
            (attempt/'capture/manifest.json').write_text(json.dumps(manifest))
            files={name:(attempt/name).read_text() for name in NAMES}
            files['acquisition-provenance.json']=json.dumps({
                'provenance_kind':'synthetic_fixture','diagnostic_fixture':True})+'\n'
            videos=[{'path':name+'.mkv','frames':480,'width':width,'height':height,
                     'fps':20,'color':'black'} for name,width,height in CAMERAS]
            target=HERE/f'update015-{suffix}-diagnostic.json'
            target.write_text(json.dumps({'files':files,'graphs':graphs,'videos':videos},
                separators=(',',':'),allow_nan=False)+'\n')
            if target.stat().st_size>=2*1024*1024:
                raise ValueError('Walk diagnostic spec exceeds text return limit')
            relative=target.relative_to(REPO).as_posix();digest=sha(target)
            recipe={'format':'worker-fixture-recipe',
                    'sources':[{'path':'diagnostic-input.json','source':relative,'sha256':digest}],
                    'generator':{'source':relative,'sha256':digest}}
            recipe_path=HERE/f'update015-{suffix}-recipe.json'
            recipe_path.write_text(json.dumps(recipe,indent=2)+'\n')
            outputs.append({'case_suffix':suffix,'frames':480,
                            'spec_bytes':target.stat().st_size,'spec_sha256':digest,
                            'recipe_sha256':sha(recipe_path)})
    (HERE/'update015-recipe-summary.json').write_text(json.dumps({
        'format':'c111256-update015-recipes','cases':outputs,
        'synthetic_diagnostic':True,'selected':False},indent=2)+'\n')
    print(json.dumps(outputs))

if __name__=='__main__':build()
