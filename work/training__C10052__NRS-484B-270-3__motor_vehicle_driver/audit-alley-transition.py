"""Independent raw-body audit of synthetic alley crossing timing pair."""
import hashlib
import json
from pathlib import Path

from audit_geometry import clipped_area

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
ROOT=REPO/'.runtime-work/c10052/alley-transition-v1'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):return json.loads(path.read_text())


def check(name,receipt):
    folder=ROOT/name
    manifest=read(folder/'alley-transition-sources.json')
    measurement=read(folder/'measurement.json')
    geometry=read(folder/'road_geometry.json')
    rows=[json.loads(line) for line in (folder/'native_samples.jsonl').read_text().splitlines()]
    assert receipt['measurement_sha256']==sha(folder/'measurement.json')
    assert receipt['source_manifest_sha256']==sha(folder/'alley-transition-sources.json')
    assert manifest['source_kind']=='synthetic_cpu_fixture'
    assert manifest['sha256']==measurement['source_sha256']
    assert all(sha(folder/name)==digest for name,digest in manifest['sha256'].items())
    assert len(rows)==480
    facility=geometry['bicycle_facility_native_xy_bounds_m']
    alley=geometry['alley_entrance_native_xy_bounds_m']
    f=[clipped_area(row['native_body_xy_m'],facility) for row in rows]
    a=[clipped_area(row['native_body_xy_m'],alley) for row in rows]
    moving=[row['speed_mps']>.1 for row in rows]
    first_f=next((i for i in range(1,480) if moving[i] and f[i-1]<=.01 and f[i]>.01),None)
    first_a=next((i for i in range(480) if moving[i] and a[i]>.01),None)
    both=sum(moving[i] and f[i]>.01 and a[i]>.01 for i in range(480))
    gap=None if first_f is None or first_a is None else round((first_a-first_f)/20,6)
    candidate=first_f is not None and first_a is not None and 0<=gap<=2 and both>0 and any(
        row['native_center_xy_m'][1]<alley[3] for row in rows[first_a:])
    assert measurement['first_facility_entry_native_frame']==(
        None if first_f is None else 100+first_f)
    assert measurement['first_alley_footprint_native_frame']==(
        None if first_a is None else 100+first_a)
    assert measurement['facility_to_alley_gap_s']==gap
    assert measurement['simultaneous_moving_overlap_frames']==both
    assert measurement['time_bounded_geometry_candidate']==candidate
    assert measurement['statutory_exception_observed']=='unresolved'
    assert measurement['native_route_identity_verified'] is False
    assert measurement['legal_verdict_claimed'] is False and measurement['accepted'] is False
    return rows,{'first_facility':first_f,'first_alley':first_a,'gap_s':gap,
                 'simultaneous':both,'candidate':candidate}


def main():
    summary=read(HERE/'alley-transition-summary.json')
    assert summary['source_root']==ROOT.relative_to(REPO).as_posix()
    assert summary['selected'] is False and summary['accepted'] is False
    near,n=check('near_alley',summary['cases']['near_alley'])
    away,a=check('away_from_alley',summary['cases']['away_from_alley'])
    assert n['candidate'] and n['simultaneous']>0 and 0<=n['gap_s']<=2
    assert not a['candidate'] and a['simultaneous']==0 and a['first_alley'] is None
    assert n['first_facility']==a['first_facility']
    for left,right in zip(near,away):
        for field in ('native_frame','time_s','speed_mps','synthetic_diagnostic'):
            assert left[field]==right[field]
        assert left['native_center_xy_m'][1]==right['native_center_xy_m'][1]
        assert left['native_center_xy_m'][0]-right['native_center_xy_m'][0]==12
        for near_vertex,away_vertex in zip(left['native_body_xy_m'],right['native_body_xy_m']):
            assert near_vertex[0]-away_vertex[0]==12
            assert near_vertex[1]==away_vertex[1]
    assert sha(ROOT/'near_alley/road_geometry.json')==sha(ROOT/'away_from_alley/road_geometry.json')
    negative=ROOT/'changed_samples'
    assert sha(negative/'native_samples.jsonl')!=read(negative/'alley-transition-sources.json')['sha256']['native_samples.jsonl']
    assert read(ROOT/'relabeled/alley-transition-sources.json')['source_kind']=='original_native'
    print(json.dumps({'passed':True,'near':n,'away':a,'negatives':2,
        'summary_sha256':sha(HERE/'alley-transition-summary.json')},sort_keys=True))


if __name__=='__main__':main()
