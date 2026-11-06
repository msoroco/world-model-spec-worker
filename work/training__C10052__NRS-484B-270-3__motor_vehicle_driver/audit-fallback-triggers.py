"""Independent raw-row audit of retained C10052 synthetic trigger crossings."""
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
ROOT=REPO/'.runtime-work/c10052/fallback-triggers-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def main():
    summary=read(HERE/'fallback-trigger-summary.json')
    assert summary['source_root']==ROOT.relative_to(REPO).as_posix()
    assert summary['physical_observation_claimed'] is False
    assert set(summary['positive'])=={'baseline','fallback1','fallback2','fallback3'}
    measured={}
    for name,receipt in summary['positive'].items():
        folder=ROOT/name
        source=read(folder/'trigger-sources.json')
        result=read(folder/'measurement.json')
        samples=rows(folder/'native_samples.jsonl')
        visibility=rows(folder/'camera_visibility.jsonl')
        assert receipt['measurement_sha256']==sha(folder/'measurement.json')
        assert receipt['source_manifest_sha256']==sha(folder/'trigger-sources.json')
        assert source['source_kind']=='synthetic_cpu_fixture'
        assert source['route_survey_passed'] is True
        assert len(samples)==len(visibility)==480
        for filename,expected in source['sha256'].items():
            assert sha(folder/filename)==expected
        assert result['source_sha256']==source['sha256']
        assert result['source_kind']=='synthetic_cpu_fixture'
        assert result['physical_observation_claimed'] is False
        assert all(row['synthetic_diagnostic'] for row in samples+visibility)
        assert [row['native_frame'] for row in samples]==[row['native_frame'] for row in visibility]
        assert [row['time_s'] for row in samples]==[row['time_s'] for row in visibility]
        stop=[]
        start=None
        for i,sample in enumerate(samples+[{'speed_mps':1}]):
            flag=sample['speed_mps']<=.1
            if flag and start is None:start=i
            if not flag and start is not None:
                stop.append((start,i))
                start=None
        a,b=max(stop,key=lambda pair:pair[1]-pair[0])
        assert result['stop_interval_frames']==[a,b]
        shift=next((i for i,row in enumerate(samples)
                    if abs(row['native_center_xy_m'][1]-samples[0]['native_center_xy_m'][1])>=.05),None)
        lead=None if shift is None else samples[shift]['native_center_xy_m'][0]-samples[0]['native_center_xy_m'][0]
        error=max(math.dist(row['native_center_xy_m'],(-12,-4)) for row in samples[a:b])
        duration=(b-a)/20
        fractions={view:sum(
            visibility[i]['views'][view]['full_body'] and visibility[i]['views'][view]['facility_edge']
            for i in range(a,b))/(b-a) for view in ('overview','facility')}
        assert lead==result['route_lead_in_before_lateral_shift_m']
        assert math.isclose(error,result['maximum_stationary_target_error_m'],abs_tol=1e-10)
        assert duration==result['longest_stationary_duration_s']
        assert fractions==result['stopped_frame_visible_fraction']
        flags=[lead is not None and lead<15,error>.25 or duration<2,min(fractions.values())<.95]
        assert flags==[result[f'fallback{i}_trigger_measured'] for i in range(1,4)]
        measured[name]={'lead_in_m':lead,'stop_error_m':error,
                        'stationary_s':duration,'visibility':fractions,'triggers':flags}
    assert measured['baseline']['triggers']==[False,False,False]
    for index in range(1,4):
        assert measured[f'fallback{index}']['triggers']==[i==index for i in range(1,4)]
    changed=ROOT/'changed_pixel_source'
    assert sha(changed/'camera_visibility.jsonl')!=read(changed/'trigger-sources.json')['sha256']['camera_visibility.jsonl']
    relabeled=ROOT/'synthetic_as_original'
    assert read(relabeled/'trigger-sources.json')['source_kind']=='original_native'
    assert all(row['synthetic_diagnostic'] for row in rows(relabeled/'native_samples.jsonl'))
    print(json.dumps({'passed':True,'variants':4,'crossings':3,'negatives':2,
                      'measurements':measured,'summary_sha256':sha(HERE/'fallback-trigger-summary.json')},
                     sort_keys=True))


if __name__=='__main__':
    main()
