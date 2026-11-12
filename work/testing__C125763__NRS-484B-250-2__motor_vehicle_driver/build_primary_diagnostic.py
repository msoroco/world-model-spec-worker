"""Create a text-only, explicitly synthetic primary saved-source diagnostic."""
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
CASE=HERE.name+'__yield_ego_left_near_time'


def dump(value):
    return json.dumps(value,indent=2,allow_nan=False)+'\n'


def lines(rows):
    return ''.join(json.dumps(row,allow_nan=False)+'\n' for row in rows)


def build():
    sys.path.insert(0,str(HERE/'tests'))
    spec=importlib.util.spec_from_file_location('test_finalizer',HERE/'tests'/'test_finalizer.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary)
        module.FinalizerTests().attempt(root)
        templates=[json.loads(s) for s in (root/'crossing_history.jsonl').read_text().splitlines()]
    construction=json.loads((HERE/'cases/yield_ego_left_near_time/construction.json').read_text())
    site=json.loads(next(f['content'] for f in construction['files'] if f['path']=='site.json'))
    import runner
    context=runner._context(site)
    context['diagnostic_source']='synthetic software test; no actual site review'
    example_spec=json.loads((REPO/'runtime/fixtures/example.json').read_text())
    example=example_spec['files']
    trace_base=json.loads(example['trace.jsonl'].splitlines()[0])
    evidence_base=json.loads(example['capture/evidence.jsonl'].splitlines()[0])
    frame_base=json.loads(example['capture/native/frames.jsonl'].splitlines()[0])
    base_graph=next(g for g in example_spec['graphs'] if g['path'].endswith('base/00038033.pkl'))
    crossing=[];controller=[];mapping=[];traces=[];evidence=[];native_frames=[];graphs=[]
    for i in range(60):
        template=templates[0 if i<30 else 1 if i==30 else 2]
        row=json.loads(json.dumps(template))
        frame=100+i;time_s=i/20
        row.update(frame=frame,time_s=time_s)
        crossing.append(row)
        controller.append({'frame':frame,'time_s':time_s,
            'ego_yield_control_active':True,'other_conflict_clear':False,
            'commands':{'ego':{'throttle':0.,'brake':1.,'speed_mps':1.}}})
        mapping.append({'video_frame':i,'carla_frame':frame,
                        'native_frame':frame,'time_s':time_s})
        trace=json.loads(json.dumps(trace_base))
        trace.update(frame=frame,time_s=time_s)
        traces.append(trace)
        item=json.loads(json.dumps(evidence_base))
        item.update(original_frame=frame,replay_frame=frame,
                    recording_time_s=time_s,replay_simulation_time_s=time_s)
        item['original_observations'].update(frame=frame,time_s=time_s)
        evidence.append(item)
        native=json.loads(json.dumps(frame_base))
        native.update(frame=frame,simulation_time=time_s,
                      base=f'graphs/base/{frame:08d}.pkl',
                      abstract=f'graphs/abstract/{frame:08d}.pkl')
        native_frames.append(native)
        attributes={key:value for key,value in base_graph['attributes'].items()
                    if key in ('frame','simulation_time_s','units','observed_evidence')}
        attributes.update(frame=frame,simulation_time_s=time_s,
                          observed_evidence=item['original_observations'])
        ego_node=next(node for node in base_graph['nodes'] if node['id']=='ego')
        graphs.append({'path':'capture/native/'+native['base'],
                       'attributes':attributes,'nodes':[ego_node],'edges':[]})
        graphs.append({'path':'capture/native/'+native['abstract'],
                       'attributes':{'frame':frame,'simulation_time_s':time_s},
                       'nodes':[],'edges':[]})
    files={'junction_context.json':dump(context),
           'crossing_history.jsonl':lines(crossing),
           'controller_history.jsonl':lines(controller),
           'video_frames.jsonl':lines(mapping),
           'trace.jsonl':lines(traces),
           'capture/evidence.jsonl':lines(evidence),
           'capture/native/frames.jsonl':lines(native_frames),
           'road.xodr':example['road.xodr'],
           'capture/recorder_info.txt':example['capture/recorder_info.txt'],
           'capture/native_map_facts.json':example['capture/native_map_facts.json']}
    manifest=json.loads(example['capture/manifest.json'])
    manifest.update(case_id=CASE,frames=60)
    manifest['sources']['road.xodr']=hashlib.sha256(files['road.xodr'].encode()).hexdigest()
    manifest['sources']['trace.jsonl']=hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()
    files['capture/manifest.json']=dump(manifest)
    videos=[{'path':name+'.mkv','frames':60,'width':size[0],'height':size[1],
             'fps':20,'color':'black'} for name,size in
            [('overview',(1920,1080)),('approach',(1280,720)),
             ('reference_corner',(1280,720)),('driver_reference',(1280,720))]]
    specification={'files':files,'graphs':graphs,'videos':videos}
    source=HERE/'diagnostic.json';source.write_text(dump(specification))
    relative=str(source.relative_to(REPO));checksum=hashlib.sha256(source.read_bytes()).hexdigest()
    recipe={'format':'worker-fixture-recipe',
            'sources':[{'path':'diagnostic-input.json','source':relative,'sha256':checksum}],
            'generator':{'source':relative,'sha256':checksum}}
    (HERE/'diagnostic-recipe.json').write_text(dump(recipe))
    return {'case_id':CASE,'frames':60,'recipe_sha256':checksum}


if __name__=='__main__':
    print(dump(build()),end='')
