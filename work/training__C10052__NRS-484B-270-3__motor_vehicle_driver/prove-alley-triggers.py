"""Retain controlled synthetic threshold crossings for three alley fallbacks."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
ROOT=REPO/'.runtime-work/c10052/alley-triggers-v1'
sys.path.insert(0,str(HERE/'native'))
from measure_alley_triggers import evaluate


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def rows(path,values):path.write_text(''.join(json.dumps(v)+'\n' for v in values))


def build(name,start=-45,speed=2.5,occluded=0):
    folder=ROOT/name;folder.mkdir()
    write(folder/'turn_geometry.json',{'turn_start_x_m':-5,'turn_radius_m':5,
        'scope':'authored route radius; Native steering unverified'})
    poses=[];views=[]
    for i in range(480):
        phase='turn' if 80<=i<160 else 'other'
        poses.append({'native_frame':100+i,'time_s':round((i+1)/20,6),
            'native_center_xy_m':[start,-1.5],
            'speed_mps':speed if phase=='turn' else 0,
            'phase':phase,'synthetic_diagnostic':True})
        views.append({'native_frame':100+i,'time_s':round((i+1)/20,6),
            'visible':not (phase=='turn' and i<80+occluded),
            'synthetic_diagnostic':True})
    rows(folder/'turn_samples.jsonl',poses)
    rows(folder/'turn_visibility.jsonl',views)
    write(folder/'alley-trigger-sources.json',{'format':'c10052-alley-trigger-sources-v1',
        'source_kind':'synthetic_cpu_fixture','sha256':{name:sha(folder/name) for name in
        ('turn_samples.jsonl','turn_geometry.json','turn_visibility.jsonl')}})
    result=evaluate(folder);write(folder/'measurement.json',result)
    return result


def main():
    if ROOT.exists():raise ValueError('Retain prior alley trigger proof')
    ROOT.mkdir(parents=True)
    outcomes={'baseline':build('baseline'),
        'short_runway':build('short_runway',start=-35),
        'fast_turn':build('fast_turn',speed=3),
        'occluded_view':build('occluded_view',occluded=8)}
    assert [outcomes['baseline'][f'fallback{i}_trigger_measured'] for i in range(1,4)]==[False]*3
    for name,i in (('short_runway',1),('fast_turn',2),('occluded_view',3)):
        assert [outcomes[name][f'fallback{j}_trigger_measured'] for j in range(1,4)]==[
            j==i for j in range(1,4)]
    changed=ROOT/'changed_source';shutil.copytree(ROOT/'baseline',changed)
    p=changed/'turn_visibility.jsonl';p.write_bytes(p.read_bytes()+b' ')
    try:evaluate(changed)
    except ValueError as e:assert 'source hash differs' in str(e)
    else:raise AssertionError('Changed annotation accepted')
    relabeled=ROOT/'synthetic_as_original';shutil.copytree(ROOT/'baseline',relabeled)
    p=relabeled/'alley-trigger-sources.json';m=json.loads(p.read_text())
    m['source_kind']='original_native';write(p,m)
    try:evaluate(relabeled)
    except ValueError as e:assert 'cannot be original Native' in str(e)
    else:raise AssertionError('Relabeled synthetic data accepted')
    summary={'format':'c10052-alley-trigger-proof-v1','source_root':ROOT.relative_to(REPO).as_posix(),
        'cases':{name:{'measurement_sha256':sha(ROOT/name/'measurement.json'),
            'source_manifest_sha256':sha(ROOT/name/'alley-trigger-sources.json')}
            for name in outcomes},'negative_count':2,'selected':False}
    write(HERE/'alley-trigger-summary.json',summary)
    print(json.dumps({'passed':True,'outcomes':outcomes,'negatives':2},sort_keys=True))


if __name__=='__main__':main()
