"""Create explicit synthetic source-shape fixtures for c(1) CPU checks."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
CASE=HERE.parent
ROOT=CASE.parents[1]
SOURCE=HERE/'selected-paragraph-d'/'witness_1'
OUT=HERE/'current-c1'
DISTANCES={'exception_3_1':61.06,'exception_3_2':60.96}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(encoded(value)+'\n')


def shift_ego(actor,x,y):
    center=actor['center_native_xyz_m']
    dx,dy=x-center[0],y-center[1]
    center[0],center[1]=x,y
    for point in actor['body_native_xyz_m']:
        point[0]=round(point[0]+dx,6)
        point[1]=round(point[1]+dy,6)


def build_one(suffix,distance,scratch):
    case_id=CASE.name+'__'+suffix
    attempt=scratch/suffix
    subprocess.run([str(ROOT/'.venv-cpu/bin/python'),str(ROOT/'runtime.py'),
        'materialize','--manifest',str(OUT/'manifest.json'),
        '--case',case_id,'--output',str(attempt)],cwd=ROOT,
        capture_output=True,text=True,check=True,timeout=120)
    dest=OUT/suffix
    construction=json.loads((dest/'primary/construction.json').read_text())
    road_content=next(item['content'] for item in construction['files'] if item['path']=='one-way-pass.xodr')
    road_source=dest/'fixture-road-source.xodr'
    road_source.write_text(road_content)
    spec=json.loads((SOURCE/'fixture-spec.json').read_text())
    files=spec['files']
    raw=[]
    for i,line in enumerate((SOURCE/'fixture-native-raw-actors.jsonl').read_text().splitlines()):
        row=json.loads(line)
        x=5+8*(i+1)/20
        blend=max(0,min(1,(x-16.2)/5,(20+distance+3.8-x)/5))
        y=round(-1.75-3.5*blend,6)
        shift_ego(row['ego'],x,y)
        row['observed_ego_lane_id']=-2 if y < -3.5 else -1
        raw.append(row)
    raw_path=dest/'fixture-native-raw-actors.jsonl'
    raw_path.write_text(''.join(json.dumps(row,sort_keys=True,allow_nan=False)+'\n' for row in raw))
    evidence=[]
    for i,line in enumerate(files['capture/evidence.jsonl'].splitlines()):
        row=json.loads(line)
        ego=raw[i]['ego']
        row['ego']['position_m']=ego['center_native_xyz_m']
        row['ego']['body_vertices_m']=ego['body_native_xyz_m']
        evidence.append(encoded(row))
    files['capture/evidence.jsonl']='\n'.join(evidence)+'\n'
    trace=[]
    for i,line in enumerate(files['trace.jsonl'].splitlines()):
        row=json.loads(line)
        x,y=raw[i]['ego']['center_native_xyz_m'][:2]
        row['position_m'][:2]=[x,y]
        row['position']['x'],row['position']['y']=x,y
        trace.append(encoded(row))
    files['trace.jsonl']='\n'.join(trace)+'\n'
    road=json.loads((attempt/'config.json').read_text())['road_sha256']
    map_data=json.loads(files['native-map-readback.json'])
    map_data['road_sha256']=road
    files['native-map-readback.json']=encoded(map_data)+'\n'
    capture_manifest=json.loads(files['capture/manifest.json'])
    capture_manifest['sources']['road.xodr']=sha(road_source)
    capture_manifest['sources']['road-source.xodr']=sha(road_source)
    capture_manifest['sources']['trace.jsonl']=hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()
    files['capture/manifest.json']=encoded(capture_manifest)+'\n'
    report=json.loads(files['native-capture-report.json'])
    report['case_id']=case_id
    report['config_sha256']=sha(attempt/'config.json')
    files['native-capture-report.json']=encoded(report)+'\n'
    review=json.loads(files['review-source.json'])
    review['case_id']=case_id
    review['raw_sha256']=sha(raw_path)
    review['map_sha256']=hashlib.sha256(files['native-map-readback.json'].encode()).hexdigest()
    review['capture_report_sha256']=hashlib.sha256(files['native-capture-report.json'].encode()).hexdigest()
    files['review-source.json']=encoded(review)+'\n'
    spec_path=dest/'fixture-spec.json'
    put(spec_path,spec)
    if spec_path.stat().st_size>2097152:
        raise ValueError('Fixture spec exceeds 2 MiB')
    recipe=json.loads((SOURCE/'fixture-recipe.json').read_text())
    for item in recipe['sources']:
        if item['path']=='native-raw-actors.jsonl':
            item['source']=str(raw_path.relative_to(ROOT))
            item['sha256']=sha(raw_path)
        elif item['path'] in ('road.xodr','road-source.xodr'):
            item['source']=str(road_source.relative_to(ROOT))
            item['sha256']=sha(road_source)
    recipe['generator']={'source':str(spec_path.relative_to(ROOT)),'sha256':sha(spec_path)}
    put(dest/'fixture-recipe.json',recipe)
    return {'case_id':case_id,'fixture_recipe_sha256':sha(dest/'fixture-recipe.json')}


def build():
    scratch=Path(os.environ['TMPDIR']).resolve()
    if ROOT/'.runtime-work' not in scratch.parents:
        raise ValueError('TMPDIR must be under .runtime-work')
    with tempfile.TemporaryDirectory(dir=scratch,prefix='c1-fixtures-') as name:
        return [build_one(suffix,distance,Path(name)) for suffix,distance in DISTANCES.items()]


if __name__=='__main__':
    print(json.dumps(build(),sort_keys=True))
