"""Independent source/hash and controlled-input audit of the two synthetic stops."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUTPUT=HERE/'draft-measurements'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit():
    plan=json.loads((HERE/'case-plan.json').read_text())
    assert plan['source_law_text']=='A person shall not stop, stand or park a vehicle within an alley in such position as to block the driveway or entrance to any abutting property.'
    assert {c['case_id'].rsplit('__',1)[-1] for c in plan['cases']}=={'reference','contrast'}
    summary=json.loads((OUTPUT/'summary.json').read_text())
    assert summary['selected'] is False and summary['ready'] is False
    assert len(summary['rows'])==2
    reviewed={}
    for suffix in ('reference','contrast'):
        folder=OUTPUT/suffix
        data=rows(folder/'native_samples.jsonl')
        geometry=json.loads((folder/'road_geometry.json').read_text())
        report=json.loads((folder/'measurement.json').read_text())
        contract=json.loads((folder/'measurement-contract.json').read_text())
        contract_report=json.loads((folder/'contract-report.json').read_text())
        assert len(data)==480
        assert report['original_frames']==480
        assert report['source_sha256']=={'native_samples.jsonl':sha(folder/'native_samples.jsonl'),
                                          'road_geometry.json':sha(folder/'road_geometry.json')}
        assert contract['case_id']==next(c['case_id'] for c in plan['cases']
                                         if c['case_id'].endswith('__'+suffix))
        assert {r['disposition_index'] for r in contract['requirements']}=={0,1}
        assert contract['negative']=={'remove':['native_samples.jsonl'],
                                      'error_contains':'Missing required source: native_samples.jsonl'}
        for item in contract_report['measurements'].values():
            assert item['sources']==report['source_sha256']
        assert geometry['native_alley_and_access_design_verified'] is False
        assert report['native_design_verified'] is False
        assert report['legal_blocking_verdict_claimed'] is False
        assert geometry['driveway_entrance_native_xy_bounds_m']==[-3.0,-4.0,3.0,0.0]
        assert geometry['abutting_property_access_native_xy_bounds_m']==[-3.0,-20.0,3.0,-4.0]
        for i,row in enumerate(data):
            assert row['native_frame']==100+i and abs(row['time_s']-(i+1)/20)<1e-10
            assert row['native_road_id']==1 and row['native_lane_id']==-1
            assert row['native_forward_xy']==[1,0] and row['native_center_xy_m'][1]==-2.0
            x=row['native_center_xy_m'][0]
            expected_body=[[x-2.6,-3.1],[x-2.6,-.9],
                           [x+2.6,-.9],[x+2.6,-3.1]]
            assert all(abs(actual[k]-expected[k])<1e-10
                       for actual,expected in zip(row['native_body_xy_m'],expected_body)
                       for k in (0,1))
            expected_speed=(x-data[i-1]['native_center_xy_m'][0])*20 if i else 0
            assert abs(row['speed_mps']-expected_speed)<1e-10
        stop=-12 if suffix=='reference' else 0
        assert data[-1]['native_center_xy_m'][0]==stop
        stationary=[i for i,row in enumerate(data) if row['speed_mps']<=.1]
        assert stationary[-1]==479
        # An independent axis-aligned overlap calculation avoids the measurement clipper.
        overlap=max(0,min(stop+2.6,3)-max(stop-2.6,-3))
        assert report['max_entrance_overlap_m']==round(overlap,6)
        assert report['mean_entrance_overlap_m']==round(overlap,6)
        assert report['stop_duration_s']>=2
        reviewed[suffix]=data
    # Until the reference stop, both cases share the same exact source pose, speed,
    # body, frame and time; only their commanded stop station differs afterwards.
    for a,b in zip(reviewed['reference'][:132],reviewed['contrast'][:132]):
        assert a==b
    assert json.loads((OUTPUT/'reference/road_geometry.json').read_text())==json.loads((OUTPUT/'contrast/road_geometry.json').read_text())
    result={'format':'c10014-independent-synthetic-pair-audit-v1',
            'source_law_sha256':hashlib.sha256(plan['source_law_text'].encode()).hexdigest(),
            'shared_prefix_frames':132,'reference_overlap_m':0,'contrast_overlap_m':5.2,
            'physical_native_claim':False,'legal_verdict_claim':False}
    (OUTPUT/'independent-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(audit(),indent=2))
