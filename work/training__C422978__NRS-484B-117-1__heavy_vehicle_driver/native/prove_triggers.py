"""Retain 12 synthetic saved-body trigger and non-trigger fixtures."""
import copy
import json
from pathlib import Path

from triggers import evaluate, sha

HERE = Path(__file__).resolve().parent
OUT = HERE / 'trigger-fixtures'


def body_rows(case, policy):
    path = HERE / 'drafts' / case / policy / 'requested-tracks.jsonl'
    requested = [json.loads(x) for x in path.read_text().splitlines()]
    result = []
    for row in requested:
        x,y = row['requested_center_xy_m']
        y = -y
        result.append({'frame':row['frame'], 'native_frame':1000+row['frame'],
                       'time_s':round(.05+row['time_s'],4), 'source_kind':'synthetic_cpu',
                       'vehicle_blueprint':'vehicle.carlamotors.carlacola',
                       'speed_mps':row['requested_speed_mps'],
                       'body_native_xy_m':[[x+dx,round(y+dy,4)] for dx,dy in
                                           ((-4,-1.2),(-4,1.2),(4,-1.2),(4,1.2))]})
    return result


def write_rows(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))


proof = []
for case in ('reference','contrast'):
    for candidate in ('fallback1','fallback2','fallback3'):
        for expected in (True,False):
            policy = 'primary'
            if case=='contrast' and not expected and candidate in ('fallback1','fallback2'):
                policy='fallback1'
            rows = body_rows(case, policy)
            if case=='reference' and expected and candidate=='fallback1':
                for point in rows[120]['body_native_xy_m']: point[1]=round(point[1]+3,4)
            if case=='reference' and expected and candidate=='fallback2':
                for row in rows:
                    for point in row['body_native_xy_m']: point[1]=round(point[1]+.4,4)
            label = 'trigger' if expected else 'clear'
            path = OUT / case / candidate / (label+'.jsonl')
            write_rows(path,rows)
            camera = None
            if candidate=='fallback3':
                source = OUT / case / candidate / (label+'-camera.txt')
                source.write_text('synthetic camera visibility '+case+' '+label+'\n')
                camera = {'source':str(source),'sha256':sha(source),
                          'source_kind':'synthetic_cpu','frames':480,
                          'visible_frames':300 if expected else 400}
            receipt = evaluate(case,candidate,path,sha(path),camera)
            assert receipt['triggered'] is expected
            proof.append({'case':case,'candidate':candidate,'expected':expected,
                          'observed_path':str(path.relative_to(HERE)),
                          'observed_sha256':sha(path), 'camera':camera,
                          'metric':receipt['metric']})
first = proof[0]
try:
    evaluate(first['case'],first['candidate'],HERE/first['observed_path'],'0'*64)
except ValueError as error:
    assert str(error)=='Observed body source hash differs'
else:
    raise AssertionError('Changed body hash accepted')
camera_case = next(x for x in proof if x['candidate']=='fallback3')
bad = copy.deepcopy(camera_case['camera']); bad['sha256']='0'*64
try:
    evaluate(camera_case['case'],camera_case['candidate'],HERE/camera_case['observed_path'],
             camera_case['observed_sha256'],bad)
except ValueError as error:
    assert str(error)=='Camera source hash differs'
else:
    raise AssertionError('Changed camera hash accepted')
output = {'format':'c422978-heavy-native-trigger-proof-v1',
          'build_manifest_sha256':sha(HERE/'drafts/manifest.json'),
          'trigger_code_sha256':sha(HERE/'triggers.py'),
          'fixtures':proof,'negative_hash_rejections':2,
          'original_native_observed':False,'delivery_or_legal_result':False}
(HERE/'trigger-proof.json').write_text(json.dumps(output,indent=2)+'\n')
print('heavy saved-body triggers: 12 fixtures, two hash negatives')
