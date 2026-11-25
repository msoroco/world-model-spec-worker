"""Build explicit synthetic transport sources for selected lamp compatibility.

These source shapes are diagnostic only. They do not establish original pixels,
official authority, or legal lamp equipment sufficiency.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

from prove_lamp_finalizer import attempt
from finalize_lamp import finalize


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def line_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def row_bytes(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n'
                   for row in rows)


def body(x, y):
    return [[x+dx, y+dy, z] for dx in (-2,2) for dy in (-1,1)
            for z in (0,1.5)]


def one(suffix, scratch):
    case = HERE.name + '__' + suffix
    target = HERE / 'cases' / suffix
    source = target / 'source'
    source.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temporary:
        temporary = Path(temporary)
        attempt(temporary, suffix)
        finalize(temporary, temporary / 'analysis.json')
        for path in temporary.iterdir():
            if path.is_file() and path.name not in ('config.json', 'analysis.json', 'result.json'):
                shutil.copyfile(path, source / path.name)
    trace = line_rows(source / 'trace.jsonl')
    frame_map = line_rows(source / 'video_frames.jsonl')
    evidence, native_frames, graphs = [], [], []
    for index, (point, mapped) in enumerate(zip(trace, frame_map)):
        frame = point['frame']
        x, y, z = (point['position'][key] for key in ('x','y','z'))
        evidence.append({'original_frame':frame, 'replay_frame':frame,
                         'actor_id':107, 'recording_time_s':point['time_s'],
                         'replay_simulation_time_s':point['time_s'],
                         'ego':{'position_m':[x,y,z], 'heading_deg':0,
                                'speed_mps':point['speed_mps'],
                                'speed_provenance':'synthetic_native_sample',
                                'body_vertices_m':body(x,y)},
                         'world':{'weather':{'cloudiness':0,'precipitation':0,
                                             'sun_altitude_angle':45},
                                  'road_projection':{'road_id':1,'section_id':0,
                                                     'lane_id':-1,'s_m':x+80}}})
        path = f'capture/native/graphs/base/{frame:08d}.adapter.json'
        native_frames.append({'frame':frame,'simulation_time':point['time_s'],
                              'abstract':None,'base':None,'nodes':1,'edges':0,
                              'extraction_seconds':0,'capture_seconds':0,
                              'adapter_graph':f'graphs/base/{frame:08d}.adapter.json'})
        graphs.append({'path':path,
                       'attributes':{'frame':frame,'simulation_time_s':point['time_s'],
                                     'synthetic_diagnostic':True},
                       'nodes':[{'id':'ego','attributes':{
                           'sem_class':'ego','entity_id':107,
                           'vertex':[x,y,z], 'forward':[1,0,0],
                           'threedbbox':body(x,y)}}], 'edges':[]})
    if len(trace) != 600 or len(frame_map) != 600:
        raise ValueError('diagnostic source must contain 600 frames')
    capture = source / 'capture'
    (capture / 'native').mkdir(parents=True, exist_ok=True)
    (capture / 'evidence.jsonl').write_text(row_bytes(evidence))
    (capture / 'native/frames.jsonl').write_text(row_bytes(native_frames))
    (capture / 'recorder_info.txt').write_text(
        'Create 107: vehicle.tesla.model3\nSynthetic CPU diagnostic only; no CARLA recording.\n')
    write(capture / 'manifest.json', {'extraction_confirmed':True,'frames':600,
          'acquisition':'synthetic_diagnostic','observation_contract_version':1,
          'required_observations':['kin.position'],
          'sources':{'road.xodr':sha(source/'road.xodr'),
                     'trace.jsonl':sha(source/'trace.jsonl')},
          'synthetic_diagnostic':True,'case_id':case})
    write(source / 'acquisition-provenance.json',
          {'case_id':case,'scope':'synthetic CPU diagnostic; not original pixels'})
    spec = {'files':{}, 'graphs':graphs,
            'videos':[{'path':name+'.mkv','frames':600,
                       'width':1920 if name=='overview' else 1280,
                       'height':1080 if name=='overview' else 720,'fps':20,
                       'color':color}
                      for name,color in zip(VIEWS,('blue','red','green','white'))]}
    write(target/'diagnostic.json',spec)
    recipe={'format':'worker-fixture-recipe',
            'sources':[{'path':path.relative_to(source).as_posix(),
                        'source':path.relative_to(ROOT).as_posix(),
                        'sha256':sha(path)}
                       for path in sorted(source.rglob('*')) if path.is_file()],
            'generator':{'source':(target/'diagnostic.json').relative_to(ROOT).as_posix(),
                         'sha256':sha(target/'diagnostic.json')}}
    write(target/'recipe.json',recipe)
    return {'case_id':case,'diagnostic_bytes':(target/'diagnostic.json').stat().st_size,
            'sources':len(recipe['sources']),'recipe_sha256':sha(target/'recipe.json')}


def main():
    sys.path.insert(0,str(ROOT / 'runtime' / 'scenario_pipeline'))
    scratch = ROOT / '.runtime-work' / 'c179824'
    scratch.mkdir(parents=True, exist_ok=True)
    cases=[one(suffix,scratch) for suffix in ('controlled_1','controlled_2')]
    print(json.dumps({'passed':True,'cases':cases,'synthetic_only':True},sort_keys=True))


if __name__ == '__main__':
    main()
