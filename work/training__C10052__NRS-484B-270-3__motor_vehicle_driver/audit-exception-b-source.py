"""Independent hash, raw response, trigger and negative audit for clause (b)."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
def bounds(poly):
    return min(x for x,y in poly),min(y for x,y in poly),max(x for x,y in poly),max(y for x,y in poly)
def overlap(poly):
    ax,ay,bx,by=bounds(poly)
    return max(0,min(bx,20)-max(ax,-15))*max(0,min(by,-3)-max(ay,-5))

def main():
    summary=read(HERE/'exception-b-source-summary.json')
    assert summary['cases']==2 and summary['candidates']==8
    assert summary['original_native_capture_executed'] is False
    pairs={}
    for item in summary['results']:
        folder=(HERE/item['receipt']).parent
        receipt=read(folder/'receipt.json')
        assert sha(folder/'receipt.json')==item['receipt_sha256']
        for field,name in (('source_sha256','source-rows.jsonl'),
            ('construction_sha256','construction.json'),('measurement_sha256','measurement.json'),
            ('trigger_sha256','trigger-measurement.json'),('negative_sha256','negative-receipts.json')):
            assert receipt[field]==sha(folder/name)
        state=item['state'];candidate=item['candidate_id']
        source=[json.loads(line) for line in (folder/'source-rows.jsonl').read_text().splitlines()]
        assert len(source)==480
        assert all(r['native_frame']==2000+i and r['time_s']==round(i/20,2)
            for i,r in enumerate(source))
        assert all(r['powertrain_readback']['drive_enabled'] is not r['fault_injection_applied']
            for r in source)
        assert all((r['powertrain_readback']['fault_code']=='synthetic_propulsion_disabled')
            ==r['fault_injection_applied'] for r in source)
        p=read(folder/'construction.json');measurement=read(folder/'measurement.json')
        trig=read(folder/'trigger-measurement.json')
        tests=[r for r in source[100:p['propulsion_test_end_frame']]
            if r['throttle_command']>=.4 and r['brake_command']==0]
        displacement=round(tests[-1]['ego_center_xy'][0]-tests[0]['ego_center_xy'][0],4)
        faults=sum(r['fault_injection_applied'] for r in source)
        occupancy=sum(overlap(r['ego_body_xy'])>0 for r in source[100:240])
        assert (faults,len(tests),displacement,occupancy)==(
            measurement['fault_readback_frames'],measurement['propulsion_test_frames'],
            measurement['propulsion_test_displacement_m'],
            measurement['bicycle_lane_occupied_frames_100_240'])
        assert faults==(280 if state=='faulted' else 0)
        assert displacement==(0 if state=='faulted' else (10.68 if candidate=='fallback2' else 7.08))
        assert occupancy==140
        assert trig['fault_observation_frames']==(0 if state=='healthy' else
            (220 if candidate=='fallback1' else 160))
        assert trig['propulsion_test_frames']==(90 if candidate=='fallback2' else 60)
        assert trig['scripted_reference_visible_fraction']==(1.0 if candidate=='fallback3' else .887324)
        assert trig['original_camera_pixels_verified'] is False
        negatives=read(folder/'negative-receipts.json')
        assert {n['kind'] for n in negatives}=={'fault_state','frame_identity'}
        assert all(n['rejected'] for n in negatives)
        pairs[state,candidate]={'source':source,'measurement':measurement}
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        faulted=pairs['faulted',candidate]['source']
        healthy=pairs['healthy',candidate]['source']
        assert all(a['native_frame']==b['native_frame'] and a['time_s']==b['time_s']
            and a['throttle_command']==b['throttle_command'] and a['brake_command']==b['brake_command']
            and a['scripted_reference_visible']==b['scripted_reference_visible']
            for a,b in zip(faulted,healthy))
        assert faulted[100]['ego_center_xy']==healthy[100]['ego_center_xy']
    result={'format':'c10052-exception-b-independent-source-audit-v1','passed':True,
        'positive_sources':8,'controlled_fault_healthy_pairs':4,
        'fault_state_negatives':8,'changed_frame_negatives':8,
        'original_native_disabled_state_verified':False,'legal_exception_verified':False,
        'selected':False,'accepted':False}
    path=HERE/'exception-b-independent-audit.json'
    path.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
