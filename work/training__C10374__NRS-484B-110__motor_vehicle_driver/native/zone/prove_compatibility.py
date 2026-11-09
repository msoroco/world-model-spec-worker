"""CPU positive and source/geometry tamper negatives for exact copied zone bundles."""
import json
from pathlib import Path
import shutil
import tempfile

from check import check

HERE=Path(__file__).resolve().parent


def rejected(bundle,change):
    with tempfile.TemporaryDirectory(prefix='c10374-negative-') as temp:
        target=Path(temp)/'bundle'
        shutil.copytree(bundle,target)
        change(target)
        try:check(target)
        except (ValueError,KeyError,TypeError):return True
        return False


def edit_json(path,key,value):
    data=json.loads(path.read_text());data[key]=value
    path.write_text(json.dumps(data)+'\n')


def edit_track(path,key,value):
    lines=path.read_text().splitlines();row=json.loads(lines[100])
    row[key]=value;lines[100]=json.dumps(row)
    path.write_text('\n'.join(lines)+'\n')


def prove():
    entries=json.loads((HERE/'offline/manifest.json').read_text())['entries']
    positives=negatives=0
    for entry in entries:
        bundle=HERE/entry['bundle']
        checked=check(bundle)
        if checked['delivery_ready'] or checked['actual_zone_overlap_observed']:
            raise ValueError('unverified status promoted')
        positives+=1
        changes=(
            lambda d:edit_json(d/'assignment-source.json','actor','pedestrian'),
            lambda d:edit_json(d/'case-plan.json','selected_branch','different'),
            lambda d:edit_json(d/'config.json','road_sha256','0'*64),
            lambda d:edit_json(d/'config.json','requested_zone_route',not checked['requested_zone_route']),
            lambda d:edit_track(d/'requested-tracks.jsonl','requested_ego_y_m',0),
            lambda d:(d/'alley-zone.xodr').write_text((d/'alley-zone.xodr').read_text().replace('id="374"','id="375"')),
        )
        for change in changes:
            if not rejected(bundle,change):raise ValueError('tamper accepted')
            negatives+=1
    result={'format':'c10374-safety-zone-copied-compatibility-v1',
            'positives':positives,'negatives':negatives,
            'original_native_observed':False,'delivery_ready':False}
    (HERE/'offline/proof-compatibility.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(prove()))
