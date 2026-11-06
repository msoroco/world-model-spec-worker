"""Independently recompute the alley turn fallback metrics from raw rows."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
ROOT=REPO/'.runtime-work/c10052/alley-triggers-v1'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):return json.loads(path.read_text())


def lines(path):return [json.loads(line) for line in path.read_text().splitlines()]


def check(name,receipt):
    folder=ROOT/name
    manifest=read(folder/'alley-trigger-sources.json')
    result=read(folder/'measurement.json')
    geometry=read(folder/'turn_geometry.json')
    poses=lines(folder/'turn_samples.jsonl')
    views=lines(folder/'turn_visibility.jsonl')
    assert receipt['measurement_sha256']==sha(folder/'measurement.json')
    assert receipt['source_manifest_sha256']==sha(folder/'alley-trigger-sources.json')
    assert manifest['source_kind']=='synthetic_cpu_fixture'
    assert manifest['sha256']==result['source_sha256']
    assert all(sha(folder/name)==digest for name,digest in manifest['sha256'].items())
    assert len(poses)==len(views)==480
    assert all(p['native_frame']==v['native_frame']==100+i and
        p['time_s']==v['time_s']==round((i+1)/20,6)
        for i,(p,v) in enumerate(zip(poses,views)))
    turn=[(p,v) for p,v in zip(poses,views) if p['phase']=='turn']
    assert len(turn)==80
    runway=geometry['turn_start_x_m']-poses[0]['native_center_xy_m'][0]
    peak=max(p['speed_mps']**2/geometry['turn_radius_m'] for p,_ in turn)
    visible=sum(v['visible'] for _,v in turn)
    assert result['approach_runway_m']==runway
    assert result['peak_lateral_accel_proxy_mps2']==round(peak,6)
    assert result['visible_turn_frames']==visible
    assert result['turn_frames']==80
    assert result['turn_visibility_fraction']==round(visible/80,6)
    assert [result[f'fallback{i}_trigger_measured'] for i in range(1,4)]==[
        runway<35,peak>1.5,visible/80<.95]
    assert result['physical_behavior_confirmed'] is False and result['accepted'] is False
    return poses,views,{'runway_m':runway,'peak_proxy_mps2':peak,
                       'visible_frames':visible,'triggers':[
                       result[f'fallback{i}_trigger_measured'] for i in range(1,4)]}


def main():
    summary=read(HERE/'alley-trigger-summary.json')
    assert summary['source_root']==ROOT.relative_to(REPO).as_posix()
    assert summary['selected'] is False and summary['negative_count']==2
    data={name:check(name,receipt) for name,receipt in summary['cases'].items()}
    assert data['baseline'][2]['triggers']==[False,False,False]
    for name,i in (('short_runway',0),('fast_turn',1),('occluded_view',2)):
        assert data[name][2]['triggers']==[j==i for j in range(3)]
    base_poses,base_views,_=data['baseline']
    for name in ('short_runway','fast_turn','occluded_view'):
        poses,views,_=data[name]
        assert sha(ROOT/name/'turn_geometry.json')==sha(ROOT/'baseline/turn_geometry.json')
        if name!='short_runway':assert all(a['native_center_xy_m']==b['native_center_xy_m']
                                           for a,b in zip(base_poses,poses))
        if name!='fast_turn':assert all(a['speed_mps']==b['speed_mps']
                                       for a,b in zip(base_poses,poses))
        if name!='occluded_view':assert base_views==views
    changed=ROOT/'changed_source'
    assert sha(changed/'turn_visibility.jsonl')!=read(changed/'alley-trigger-sources.json')['sha256']['turn_visibility.jsonl']
    assert read(ROOT/'synthetic_as_original/alley-trigger-sources.json')['source_kind']=='original_native'
    print(json.dumps({'passed':True,'metrics':{name:value[2] for name,value in data.items()},
        'negative_count':2,'summary_sha256':sha(HERE/'alley-trigger-summary.json')},sort_keys=True))


if __name__=='__main__':main()
