"""Independent raw-vertex and held-variable audit of C10052 moving entry."""
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
ROOT=REPO/'.runtime-work/c10052/moving-entry-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def area(body,facility):
    xs=[point[0] for point in body];ys=[point[1] for point in body]
    return max(0,min(max(xs),facility[2])-max(min(xs),facility[0]))*max(
        0,min(max(ys),facility[3])-max(min(ys),facility[1]))


def audit(name,receipt):
    folder=ROOT/name
    source=read(folder/'entry-sources.json')
    result=read(folder/'measurement.json')
    geometry=read(folder/'road_geometry.json')
    samples=rows(folder/'native_samples.jsonl')
    assert receipt['measurement_sha256']==sha(folder/'measurement.json')
    assert receipt['source_manifest_sha256']==sha(folder/'entry-sources.json')
    assert source['source_kind']=='synthetic_cpu_fixture'
    assert source['sha256']==result['source_sha256']
    for filename,digest in source['sha256'].items():assert sha(folder/filename)==digest
    assert len(samples)==result['original_frames']==480
    assert geometry['native_facility_design_verified'] is False
    assert all(row['synthetic_diagnostic'] is True for row in samples)
    assert [row['native_frame'] for row in samples]==list(range(100,580))
    assert all(math.isclose(row['time_s'],(i+1)/20,abs_tol=1e-8)
               for i,row in enumerate(samples))
    facility=geometry['bicycle_facility_native_xy_bounds_m']
    areas=[area(row['native_body_xy_m'],facility) for row in samples]
    moving=[row['speed_mps']>.1 for row in samples]
    first=next((i for i in range(1,480)
                if areas[i-1]<=.01 and areas[i]>.01 and moving[i]),None)
    occupied=sum(flag and value>.01 for flag,value in zip(moving,areas))
    maximum=max((value for flag,value in zip(moving,areas) if flag),default=0)
    assert result['moving_entry_measured']==(first is not None)
    assert result['first_moving_entry_native_frame']==(
        None if first is None else samples[first]['native_frame'])
    assert result['moving_occupied_frames']==occupied
    assert math.isclose(result['maximum_moving_overlap_m2'],maximum,abs_tol=1e-6)
    assert result['facility_designation_verified'] is False
    assert result['exception_a_observed']=='unresolved'
    assert result['legal_verdict_claimed'] is False and result['accepted'] is False
    return samples,{'first_frame':result['first_moving_entry_native_frame'],
                    'moving_occupied_frames':occupied,'max_overlap_m2':maximum}


def main():
    summary=read(HERE/'moving-entry-summary.json')
    assert summary['source_root']==ROOT.relative_to(REPO).as_posix()
    assert summary['selected'] is False and summary['accepted'] is False
    assert set(summary['cases'])=={'no_entry','moving_entry'}
    base,base_measure=audit('no_entry',summary['cases']['no_entry'])
    crossing,cross_measure=audit('moving_entry',summary['cases']['moving_entry'])
    assert base_measure['first_frame'] is None and base_measure['moving_occupied_frames']==0
    assert cross_measure['first_frame']==185 and cross_measure['moving_occupied_frames']==48
    for left,right in zip(base,crossing):
        for key in ('native_frame','time_s','speed_mps','native_road_id','native_forward_xy'):
            assert left[key]==right[key]
        assert left['native_center_xy_m'][0]==right['native_center_xy_m'][0]
    assert sha(ROOT/'no_entry/road_geometry.json')==sha(ROOT/'moving_entry/road_geometry.json')
    changed=ROOT/'changed_source'
    assert sha(changed/'native_samples.jsonl')!=read(changed/'entry-sources.json')['sha256']['native_samples.jsonl']
    relabeled=ROOT/'synthetic_as_original'
    assert read(relabeled/'entry-sources.json')['source_kind']=='original_native'
    assert all(row['synthetic_diagnostic'] for row in rows(relabeled/'native_samples.jsonl'))
    print(json.dumps({'passed':True,'comparison':{'no_entry':base_measure,
        'moving_entry':cross_measure},'held_source_fields':True,'negatives':2,
        'designation_verified':False,'legal_verdict_claimed':False,
        'summary_sha256':sha(HERE/'moving-entry-summary.json')},sort_keys=True))


if __name__=='__main__':main()
