"""Exercise the exact raw-to-saved bridge with diagnostic sources and negatives."""
import copy
import json
from pathlib import Path
import tempfile

import capture
import measure_raw
import prepare_raw
from prove_capture_measure import fixture

ROOT=Path(__file__).resolve().parent


def write(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n')


def write_rows(path,rows):
    path.write_text(''.join(json.dumps(row,allow_nan=False)+'\n' for row in rows))


def raw_fixture(bundle,folder):
    cfg=json.loads((bundle/'config.json').read_text())
    track=measure_raw.read_jsonl(bundle/'requested-tracks.jsonl')
    rows,frames=fixture(track)
    write_rows(folder/'native-raw-actors.jsonl',rows)
    write_rows(folder/'video_frames.jsonl',frames)
    write(folder/'native-map-readback.json',{
        'source_kind':'synthetic_native_sample','road_sha256':cfg['road_sha256'],
        'native_map_sha256':'a'*64,
        'driving_lane_readback':{str(n):{'road_id':210,'lane_id':n} for n in (-1,-2)},
        'ego_actor_id':1,'lead_actor_id':2,'legal_verdict':None})
    write(folder/'native-capture-report.json',{
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'config_sha256':capture.sha(bundle/'config.json'),
        'requested_frames':240,'observed_frames':240,
        'error':None,'accepted':False,'delivery_ready':False,
        'legal_safety_verdict':None})
    return rows,frames


def rejected(bundle,folder,output,synthetic,label):
    try:prepare_raw.prepare(bundle,folder,output,synthetic)
    except (ValueError,KeyError,FileNotFoundError):return label
    raise AssertionError('Raw-source negative accepted: '+label)


def prove():
    positive=[];negative=[]
    with tempfile.TemporaryDirectory() as temporary:
        base=Path(temporary)
        for witness in ('reference','contrast'):
            for candidate in ('primary','fallback1','fallback2','fallback3'):
                bundle=ROOT/'drafts'/witness/candidate
                raw=base/witness/candidate/'raw';raw.mkdir(parents=True)
                rows,frames=raw_fixture(bundle,raw)
                receipt=prepare_raw.prepare(bundle,raw,raw.parent/'saved',True)
                assert receipt['source_kind']=='synthetic_native_sample'
                assert not receipt['original_native_observed'] and not receipt['delivery_ready']
                measured=json.loads((raw.parent/'saved'/'right-pass-measures.json').read_text())
                assert measured['diagnostic_only'] and measured['observed_right_pass_frames']>0
                positive.append([witness,candidate,measured['minimum_pass_body_surface_gap_m']])
                if witness=='reference' and candidate=='primary':
                    bad=copy.deepcopy(rows);bad[30]['ego']['actor_id']=999
                    write_rows(raw/'native-raw-actors.jsonl',bad)
                    negative.append(rejected(bundle,raw,raw.parent/'bad-actor',True,'changed-actor-id'))
                    write_rows(raw/'native-raw-actors.jsonl',rows)
                    bad=copy.deepcopy(rows);bad[40]['requested_lead_x_m']+=1
                    write_rows(raw/'native-raw-actors.jsonl',bad)
                    negative.append(rejected(bundle,raw,raw.parent/'bad-request',True,'changed-request-join'))
                    write_rows(raw/'native-raw-actors.jsonl',rows)
                    bad=copy.deepcopy(frames);bad[50]['native_frame']+=1
                    write_rows(raw/'video_frames.jsonl',bad)
                    negative.append(rejected(bundle,raw,raw.parent/'bad-frame',True,'changed-camera-frame'))
                    write_rows(raw/'video_frames.jsonl',frames)
                    negative.append(rejected(bundle,raw,raw.parent/'bad-original',False,'synthetic-as-original'))
    return {'positive_synthetic_raw_to_saved':positive,
            'negative_rejections':negative,'original_native_observed':False,
            'legal_safety_verdict':None}


if __name__=='__main__':
    print(json.dumps(prove(),sort_keys=True))
