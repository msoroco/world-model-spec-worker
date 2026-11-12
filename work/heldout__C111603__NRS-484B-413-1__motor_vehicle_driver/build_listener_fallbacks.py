"""Author three distinct physical-risk fallbacks per listener distance point."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def save(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n')


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


for offset in (2,4,6):
    prefix=f'listener-{offset}m'
    construction=json.loads((HERE/f'{prefix}-construction.json').read_text())
    manifest_path=HERE/f'{prefix}-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    entry=manifest['cases'][0]
    entry['candidates']=[]
    for number in (1,2,3):
        candidate=deepcopy(construction)
        files={row['path']:row for row in candidate['files']}
        if number==1:
            config=json.loads(files['config.json']['content'])
            config.setdefault('engineering',{})['route_candidate_index']=1
            files['config.json']['content']=json.dumps(config,indent=2)+'\n'
            trigger={'source':'Native connected-route and sidewalk waypoint inventory',
                     'metric':'spawnable sidewalk waypoint at requested route-relative offset',
                     'failure_condition':'Primary selected route has no suitable sidewalk listener spawn'}
            changed=['connected left-turn route candidate index 0 to 1; requested listener offset fixed']
        elif number==2:
            runner=files['runner.py']
            old="ListenerCaptureProcess(output / 'listener.wav', device=require_microphone_device())"
            if runner['content'].count(old)!=1: raise ValueError('Listener capture source changed')
            runner['content']=runner['content'].replace(old,
                "ListenerCaptureProcess(output / 'listener.wav', device=require_microphone_device(), sample_rate_hz=32000)")
            trigger={'source':'Original listener microphone PCM',
                     'metric':'20 Hz listener audio packet continuity',
                     'failure_condition':'Primary capture device loses or misaligns original listener PCM'}
            changed=['listener PCM rate 16000 to 32000 Hz']
        else:
            camera=files['turn_camera_capture.py']
            old='"overview": ((-8, 0, 8), (-12, 0, 0), (1920, 1080), 95),'
            if camera['content'].count(old)!=1: raise ValueError('Overview camera source changed')
            camera['content']=camera['content'].replace(old,
                '"overview": ((-9, 0, 8), (-12, 0, 0), (1920, 1080), 95),')
            trigger={'source':'Original overview RGB stream', 'metric':'pedestrian visible pixel coverage',
                     'failure_condition':'Primary overview crops the sidewalk listener'}
            changed=['overview camera mount x -8 to -9 m']
        name=f'fallback{number}'
        path=HERE/f'{prefix}-{name}-construction.json'
        save(path,candidate)
        entry['candidates'].append({'id':name,'construction':path.name,
            'construction_sha256':sha(path),'trigger':trigger,'changed_knobs':changed})
    save(manifest_path,manifest)
    print(prefix,'three_distinct_fallbacks_authored')
