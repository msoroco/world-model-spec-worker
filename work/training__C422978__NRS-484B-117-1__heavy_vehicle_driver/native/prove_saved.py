"""Retain synthetic saved-source positives and semantic negatives for eight bundles."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from measure_saved import SOURCES, measure

HERE = Path(__file__).resolve().parent
CASES = ('reference','contrast')
CANDIDATES = ('primary','fallback1','fallback2','fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))


def fixture(case,candidate):
    source = HERE/'drafts'/case/candidate
    target = HERE/'saved-fixtures'/case/candidate
    target.mkdir(parents=True,exist_ok=True)
    requests = [json.loads(line) for line in (source/'requested-tracks.jsonl').read_text().splitlines()]
    actor, video, evidence = [], [], []
    for row in requests:
        index = row['frame']
        x, authored_y = row['requested_center_xy_m']
        y = -authored_y
        actor.append({'frame':index,'native_frame':1000+index,
                      'time_s':round(.05+index/20,4),'source_kind':'synthetic_cpu',
                      'vehicle_blueprint':'vehicle.carlamotors.carlacola',
                      'center_native_xy_m':[x,y],
                      'body_native_xy_m':[[round(x-4,4),round(y-1.2,4)],
                                          [round(x-4,4),round(y+1.2,4)],
                                          [round(x+4,4),round(y-1.2,4)],
                                          [round(x+4,4),round(y+1.2,4)]],
                      'speed_mps':row['requested_speed_mps'],
                      'native_lane_id':-2 if 3.5<=y<=7.5 else -1})
        video.append({'video_frame':index,'native_frame':1000+index,
                      'carla_frame':1000+index,'time_s':round(.05+index/20,4)})
        evidence.append({'original_frame':1000+index,
                         'recording_time_s':round(.05+index/20,4)})
    write_rows(target/'native-observed.jsonl',actor)
    write_rows(target/'video_frames.jsonl',video)
    write_rows(target/'capture/evidence.jsonl',evidence)
    (target/'native-map-readback.json').write_text(json.dumps({
        'sidewalk_road_id':1,'sidewalk_lane_id':-2,
        'subject_blueprint':'vehicle.carlamotors.carlacola',
        'observed_body_width_m':2.4,'city_location_verified':False,
        'source_kind':'synthetic_cpu'},indent=2)+'\n')
    (target/'native-capture-report.json').write_text(json.dumps({
        'case_id':source.parent.parent.parent.parent.name+'__'+case,
        'candidate_id':candidate,'bundle_config_sha256':sha(source/'config.json'),
        'requested_frames':480,'observed_frames':480,'restoration':None,
        'error':None,'accepted':False,'source_kind':'synthetic_cpu'},indent=2)+'\n')
    return target


def rejected(fn):
    try:
        fn()
    except (ValueError,TypeError):
        return True
    raise AssertionError('Altered saved source accepted')


def prove():
    positives, negatives = [], []
    for case in CASES:
        for candidate in CANDIDATES:
            folder = fixture(case,candidate)
            result = measure(folder)
            if (result['frames'] != 480 or result['source_kind'] != 'synthetic_cpu' or
                    result['city_sidewalk_verified'] or result['legal_verdict'] is not None or
                    (case=='reference' and result['moving_sidewalk_overlap_frames'] != 0) or
                    (case=='contrast' and result['full_body_inside_sidewalk_frames'] < 370)):
                raise AssertionError('Synthetic saved positive differs')
            positives.append({'case':case,'candidate':candidate,'measurement':result})
            with tempfile.TemporaryDirectory(dir=HERE) as temp:
                copy = Path(temp)/'copy'
                shutil.copytree(folder,copy)
                path = copy/'native-observed.jsonl'
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                rows[0]['center_native_xy_m'][1] += .5
                write_rows(path,rows)
                negatives.append({'case':case,'candidate':candidate,
                                  'mutation':'body_center', 'rejected':rejected(lambda:measure(copy))})
                negatives.append({'case':case,'candidate':candidate,
                                  'mutation':'source_hash',
                                  'rejected':rejected(lambda:measure(copy,result['source_hashes']))})
            for name,key,mutation in (
                    ('video_frames.jsonl','native_frame','video_join'),
                    ('capture/evidence.jsonl','original_frame','capture_join')):
                with tempfile.TemporaryDirectory(dir=HERE) as temp:
                    copy = Path(temp)/'copy'
                    shutil.copytree(folder,copy)
                    path = copy/name
                    rows = [json.loads(line) for line in path.read_text().splitlines()]
                    rows[0][key] += 1
                    write_rows(path,rows)
                    negatives.append({'case':case,'candidate':candidate,
                                      'mutation':mutation,'rejected':rejected(lambda:measure(copy))})
            with tempfile.TemporaryDirectory(dir=HERE) as temp:
                copy = Path(temp)/'copy'
                shutil.copytree(folder,copy)
                path = copy/'native-map-readback.json'
                map_record = json.loads(path.read_text())
                map_record['observed_body_width_m'] = 3.1
                path.write_text(json.dumps(map_record)+'\n')
                negatives.append({'case':case,'candidate':candidate,
                                  'mutation':'width_readback','rejected':rejected(lambda:measure(copy))})
    proof = {'format':'c422978-heavy-saved-cpu-proof-v1',
             'processor_sha256':sha(HERE/'measure_saved.py'),
             'positives':positives,'negatives':negatives,
             'original_native_observed':False,'delivery_ready':False}
    (HERE/'saved-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof


if __name__ == '__main__':
    result = prove()
    print(json.dumps({'positives':len(result['positives']),
                      'negatives':len(result['negatives'])}))
