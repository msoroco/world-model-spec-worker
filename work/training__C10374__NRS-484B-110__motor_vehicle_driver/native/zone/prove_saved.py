"""Prove copied zone raw preparation and reject changed evidence."""
import json
from pathlib import Path
import shutil
import tempfile

from saved import measure,prepare
from route_fallbacks import route

HERE=Path(__file__).resolve().parent


def edit_json(path,key,value):
    data=json.loads(path.read_text());data[key]=value
    path.write_text(json.dumps(data)+'\n')


def edit_row(path,key,value):
    lines=path.read_text().splitlines();row=json.loads(lines[100])
    row[key]=value;lines[100]=json.dumps(row)
    path.write_text('\n'.join(lines)+'\n')


def rejected(bundle,raw,change,original=False):
    with tempfile.TemporaryDirectory(prefix='c10374-saved-negative-') as temp:
        target=Path(temp)/'raw';shutil.copytree(raw,target);change(target)
        try:prepare(bundle,target,Path(temp)/'saved',synthetic=not original)
        except (ValueError,KeyError,TypeError,FileNotFoundError):return True
        return False


def original_without_media(target):
    edit_json(target/'native-map-readback.json','source_kind','original_native')
    for name in ('native-raw-actors.jsonl','frame-review.jsonl'):
        path=target/name;data=[json.loads(x) for x in path.read_text().splitlines()]
        for row in data:
            row['source_kind']='original_native'
            if name=='frame-review.jsonl':row['review_provenance']='human_frame_review'
        path.write_text(''.join(json.dumps(x)+'\n' for x in data))


def prove():
    copied=json.loads((HERE/'offline/manifest.json').read_text())
    positives=negatives=0
    for entry in copied['entries']:
        bundle=HERE/entry['bundle'];suffix=bundle.parent.name;candidate=bundle.name
        raw=HERE/'offline/raw-fixtures'/suffix/candidate
        saved=HERE/'offline/saved-fixtures'/suffix/candidate
        m=measure(bundle,saved);r=route(bundle,saved)
        if m['source_kind']!='synthetic_cpu' or m['delivery_ready'] or \
           m['authored_rectangle_is_designated_zone'] or r['selected_fallback'] is not None:
            raise ValueError('synthetic saved positive')
        positives+=1
        changes=(
            lambda d:edit_json(d/'native-map-readback.json','road_sha256','0'*64),
            lambda d:edit_json(d/'native-map-readback.json','lane_readback',{}),
            lambda d:edit_json(d/'native-map-readback.json','native_zone_delimiters',[]),
            lambda d:edit_json(d/'native-capture-report.json','config_sha256','0'*64),
            lambda d:edit_row(d/'native-raw-actors.jsonl','observed_lane_id',0),
            lambda d:edit_row(d/'video_frames.jsonl','native_frame',-1),
            lambda d:edit_row(d/'frame-review.jsonl','review_provenance','claimed_human'),
            lambda d:edit_row(d/'frame-review.jsonl','zone_boundary_pixel_reviewed','yes'),
        )
        for change in changes:
            if not rejected(bundle,raw,change):raise ValueError('tampered raw accepted')
            negatives+=1
        if not rejected(bundle,raw,original_without_media,original=True):
            raise ValueError('missing original FFV1 accepted')
        negatives+=1
    result={'format':'c10374-zone-saved-compatibility-v1',
            'positive':positives,'tamper_negative':negatives,
            'original_native_observed':False,'delivery_ready':False}
    (HERE/'offline/saved-compatibility.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(prove()))
