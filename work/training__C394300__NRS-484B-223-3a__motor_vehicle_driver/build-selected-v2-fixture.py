"""Bind 480 saved synthetic rows to the current explicit-source v2 fixture recipe."""
import hashlib
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CAMERAS=(('overview',1920,1080,'blue'),('approach',1280,720,'green'),
         ('reference_corner',1280,720,'white'),('driver_reference',1280,720,'red'))


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def source_attempt(case):
    log=HERE/f'probe-package-{case}-primary.log'
    line=log.read_text().splitlines()[0]
    if not line.startswith('scratch '):raise ValueError('Exact primary scratch receipt missing')
    path=Path(line[8:])/'fixture'
    if not path.is_dir():raise ValueError('Saved primary source absent')
    return path


def build(case):
    source=source_attempt(case);destination=HERE/'selected-v2-source'/case
    destination.mkdir(parents=True,exist_ok=True)
    names=['trace.jsonl','video_frames.jsonl','native_samples.jsonl','body_history.jsonl',
        'declared_purpose.json','road_geometry.json','road.xodr','scene.xodr',
        'acquisition-provenance.json','capture/manifest.json','capture/recorder_info.txt',
        'capture/evidence.jsonl','capture/native/frames.jsonl']
    names.extend(str(p.relative_to(source)) for p in sorted((source/'channels').glob('*.jsonl')))
    sources=[]
    for name in names:
        src=source/name;target=destination/name;target.parent.mkdir(parents=True,exist_ok=True)
        if name=='capture/native/frames.jsonl':
            rows=[json.loads(line) for line in src.read_text().splitlines()]
            if len(rows)!=480:raise ValueError('Original saved Native frame count differs')
            for index,row in enumerate(rows):
                if row['frame']!=index:raise ValueError('Native frame order differs')
                row.pop('base',None);row.pop('abstract',None)
                row['adapter_graph']=f'graphs/base/{index:08d}.adapter.json'
            target.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        else:shutil.copyfile(src,target)
        if target.stat().st_size>2*1024*1024:raise ValueError('Returned source file exceeds 2 MiB')
        sources.append({'path':name,'source':str(target.relative_to(ROOT)),'sha256':sha(target)})
    graphs=[{'path':f'capture/native/graphs/base/{index:08d}.adapter.json',
             'attributes':{'frame':index},'nodes':[],'edges':[]} for index in range(480)]
    videos=[{'path':name+'.mkv','frames':480,'width':width,'height':height,'fps':20,'color':color}
            for name,width,height,color in CAMERAS]
    spec={'files':{},'graphs':graphs,'videos':videos}
    spec_path=HERE/f'selected-v2-{case}-generator.json'
    spec_path.write_text(json.dumps(spec,separators=(',',':'))+'\n')
    if spec_path.stat().st_size>2*1024*1024:raise ValueError('Generator spec exceeds 2 MiB')
    recipe={'format':'worker-fixture-recipe','sources':sources,
            'generator':{'source':str(spec_path.relative_to(ROOT)),'sha256':sha(spec_path)}}
    recipe_path=HERE/f'selected-v2-{case}-recipe.json'
    recipe_path.write_text(json.dumps(recipe,indent=2)+'\n')
    return {'case':case,'source_count':len(sources),'graph_count':len(graphs),
            'video_count':len(videos),'recipe_sha256':sha(recipe_path),'generator_sha256':sha(spec_path)}


if __name__=='__main__':print(json.dumps([build(c) for c in ('controlled_1','controlled_2')]))
