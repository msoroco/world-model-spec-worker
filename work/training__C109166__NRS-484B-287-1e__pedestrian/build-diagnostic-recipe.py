"""Source-shaped 600-frame diagonal fixtures; no physical authority claim."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT/'work/training__C10316__NRS-484B-283-1d3__pedestrian/diagnostic30-controlled_1.json'
ROAD_SHAPE = ROOT/'work/training__C111334__NRS-484B-307-4b__pedestrian/native/road.xodr'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def lines(values):
    return ''.join(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n' for value in values)


def point(index):
    fraction = min(1, max(0, (index-100)/240))
    xy = -6 + fraction*12
    return [xy, xy]


def body(xy):
    return [[xy[0]+dx, xy[1]+dy] for dx,dy in ((-.2,-.2),(.2,-.2),(.2,.2),(-.2,.2))]


def body3(xy):
    return [[xy[0]+dx, xy[1]+dy, z] for dx,dy in ((-.2,-.2),(.2,-.2),(.2,.2),(-.2,.2)) for z in (0,1.8)]


def build():
    original = json.loads(SOURCE.read_text())
    for suffix in ('controlled_1','controlled_2'):
        spec = {'files': {key:value for key,value in original['files'].items()
                          if key not in ('no-countdown-context.json','no-countdown-samples.jsonl')},
                'graphs': original['graphs'], 'videos': original['videos']}
        trace = rows(spec['files']['trace.jsonl'])
        evidence = rows(spec['files']['capture/evidence.jsonl'])
        frames = rows(spec['files']['capture/native/frames.jsonl'])
        mapping = rows(spec['files']['video_frames.jsonl'])
        if not len(trace)==len(evidence)==len(frames)==len(mapping)==len(spec['graphs'])==600:
            raise ValueError('borrowed fixture shape lacks 600 complete source frames')
        people,devices,cameras=[],[],[]
        for i in range(600):
            xy=point(i); footprint=body(xy); frame=100+i; time=i/20
            speed=2**.5 if 100 <= i < 340 else 0
            trace[i].update(frame=frame,time_s=time,position={'x':xy[0],'y':xy[1],'z':.5},
                            position_m=[*xy,.5],heading_deg=45,speed_mps=speed,
                            speed_mph=speed*2.2369362921,velocity_mps=[1 if speed else 0,1 if speed else 0,0])
            evidence[i].update(original_frame=frame,replay_frame=frame,recording_time_s=time,
                               replay_simulation_time_s=time)
            evidence[i]['ego'].update(position_m=[*xy,.5],heading_deg=45,speed_mps=speed,
                                      body_vertices_m=body3(xy))
            graph=spec['graphs'][i]
            graph['attributes'].update(frame=frame,simulation_time_s=time,
                                       source='C109166 synthetic diagonal source shape')
            graph['nodes'][0]['attributes'].update(vertex=[*xy,.5],forward=[2**-.5,2**-.5,0],
                                                   threedbbox=body3(xy))
            frames[i].update(frame=frame,time_s=time,simulation_time=time,
                             adapter_graph=f'graphs/base/{frame:08d}.adapter.json')
            graph['path']=f'capture/native/graphs/base/{frame:08d}.adapter.json'
            mapping[i].update(video_frame=i,native_frame=frame,carla_frame=frame,time_s=time)
            state='diagonal_dont_walk' if suffix=='controlled_2' and 100<=i<160 else 'diagonal_walk'
            people.append({'native_frame':frame,'time_s':time,'walker_id':107,
                           'center_xy_m':xy,'footprint_xy_m':footprint,
                           'road_entry_proxy_observed':i==100,
                           'road_boundary_review_pending':True})
            devices.append({'native_frame':frame,'time_s':time,
                            'device_id':'c109166-diagonal-crossing-head',
                            'source_kind':'native_device_readback',
                            'displayed_instruction':state,
                            'source_ref':f'synthetic-device-face/{frame}',
                            'synthetic_diagnostic':True})
            for name,width,height in (('overview',1920,1080),('approach',1280,720),
                                      ('reference_corner',1280,720),('driver_reference',1280,720)):
                cameras.append({'camera':name,'frame':i,'native_frame':frame,'time_s':time,
                                'width':width,'height':height,'source_path':name+'.mkv',
                                'source_sha256':'a'*64})
        for name,data in (('trace.jsonl',trace),('capture/evidence.jsonl',evidence),
                          ('capture/native/frames.jsonl',frames),('video_frames.jsonl',mapping),
                          ('pedestrian-original.jsonl',people),('device-original.jsonl',devices),
                          ('camera-sources.jsonl',cameras)):
            spec['files'][name]=lines(data)
        authority={}
        for name in ('authorization','official_status','movement_applicability'):
            path='authority/'+name+'.json'
            content=json.dumps({'synthetic_diagnostic':True,'requested_source':name})+'\n'
            spec['files'][path]=content
            authority[name]={'path':path,'sha256':hashlib.sha256(content.encode()).hexdigest(),
                             'device_id':'c109166-diagonal-crossing-head',
                             'movement_id':'c109166-diagonal-sw-ne',
                             'review_status':'pending_independent_review'}
        spec['files']['authority-receipt.json']=json.dumps(authority, separators=(',',':'))+'\n'
        road = ROAD_SHAPE.read_text().replace('C111334', 'C109166-synthetic-diagnostic')
        spec['files']['road.xodr'] = road
        spec['files']['capture/manifest.json']=json.dumps({'extraction_confirmed':True,
            'frames':600,'required_observations':[],
            'sources':{'trace.jsonl':hashlib.sha256(spec['files']['trace.jsonl'].encode()).hexdigest(),
                       'road.xodr':hashlib.sha256(road.encode()).hexdigest()},
            'synthetic_diagnostic':True})+'\n'
        for video in spec['videos']:
            video['frames']=600
        dest=HERE/f'diagnostic-{suffix}.json'
        dest.write_text(json.dumps(spec, separators=(',',':'), allow_nan=False)+'\n')
        recipe={'format':'worker-fixture-recipe',
                'sources':[{'path':'diagnostic-input.json',
                            'source':str(dest.relative_to(ROOT)), 'sha256':sha(dest)}],
                'generator':{'source':str(dest.relative_to(ROOT)), 'sha256':sha(dest)}}
        (HERE/f'diagnostic-{suffix}-recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
        print(json.dumps({'case':suffix,'spec_bytes':dest.stat().st_size,
                          'recipe_sha256':sha(HERE/f'diagnostic-{suffix}-recipe.json')}))


if __name__=='__main__':
    build()
