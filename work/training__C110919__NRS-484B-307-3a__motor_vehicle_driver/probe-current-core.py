"""Source-only current Core diagnostic for the two unselected primary drafts."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.runtime_cli import execution_env,process,render
from worker_exchange.media import audit

spec=importlib.util.spec_from_file_location('fixture',HERE/'saved-fixture-proof.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',choices=('witness_1','witness_2'),required=True)
    args=parser.parse_args()
    scratch=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c110919-3a-current-core-'))
    attempt=scratch/'attempt';fixture.make_attempt(attempt,args.case)
    construction=json.loads((HERE/'draft-candidates'/args.case/'primary/construction.json').read_text())
    for item in construction['files']:
        path=attempt/item['path'];path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(item['content'])
    if (attempt/'channels').exists() or (attempt/'context.json').exists():
        raise AssertionError('Fixture prepopulates derived observations')
    shutil.copyfile(HERE/'native/road.xodr',attempt/'road.xodr')
    native=rows(attempt/'native_samples.jsonl')
    mapping=rows(attempt/'video_frames.jsonl')
    graph_dir=attempt/'capture/native/graphs/base';graph_dir.mkdir(parents=True)
    frames=[]
    for sample,item in zip(native,mapping):
        frame=sample['native_frame'];time=sample['time_s']
        x,y=sample['native_center_xy_m'];heading=sample['native_yaw_deg']
        graph={'format':'native-adapter-graph-v1','multigraph':False,
            'metadata':{'frame':frame,'simulation_time_s':time},
            'nodes':[{'id':'ego','attributes':{'vertex':[x,y,.5],
                'sem_class':'ego','forward':[math.cos(math.radians(heading)),
                math.sin(math.radians(heading)),0.0],
                'entity_id':107,'carla_speed':sample['speed_mps'],
                'special_class':'ego'}}], 'edges':[]}
        rel=f'graphs/base/{frame:08d}.adapter.json'
        (attempt/'capture/native'/rel).write_text(json.dumps(graph,separators=(',',':'))+'\n')
        frames.append({'frame':frame,'simulation_time':time,'time_s':time,
                       'adapter_graph':rel,'synthetic_diagnostic':True})
    fixture.write_rows(attempt/'capture/native/frames.jsonl',frames)
    manifest=json.loads((attempt/'capture/manifest.json').read_text())
    manifest['sources']={'road.xodr':sha(attempt/'road.xodr'),
                         'trace.jsonl':sha(attempt/'trace.jsonl')}
    (attempt/'capture/manifest.json').write_text(json.dumps(manifest))
    subprocess.run([sys.executable,str(attempt/'finalize.py'),'--attempt',str(attempt),
                    '--output',str(attempt/'analysis-report.json')],cwd=attempt,
                    env=execution_env(),check=True,timeout=300,
                    stdout=subprocess.DEVNULL)
    report=json.loads((attempt/'analysis-report.json').read_text())
    derived=report['derived_channels']
    if len(derived['channel_hashes'])!=10 or any(len(rows(attempt/'channels'/(name+'.jsonl')))!=600
                                          for name in derived['channel_hashes']):
        raise AssertionError('Source-derived channels incomplete')
    core=process(attempt,attempt/'converted',ROOT/'runtime/pipeline/library',
                 ROOT/'.runtime-work/c104538-decoder/.lake/build/bin/adapterCheck',
                 diagnostic_fixture=True)
    config=json.loads((attempt/'config.json').read_text())
    video=render(attempt,attempt/'converted',config['case'])
    decoded=audit(video['video'],600,mapping_sha256=video['frame_map_sha256'],
                  receipt=attempt/'final-decode.json')
    print(json.dumps({'scratch':str(scratch),'case':args.case,'core':core,
                      'render_frames':video['frames'],'final_decode_passed':decoded['passed'],
                      'derived_channel_count':len(derived['channel_hashes']),
                      'analysis_sha256':sha(attempt/'analysis-report.json'),
                      'selected':False,'native_executed':False,'accepted':False},indent=2))

if __name__=='__main__':main()
