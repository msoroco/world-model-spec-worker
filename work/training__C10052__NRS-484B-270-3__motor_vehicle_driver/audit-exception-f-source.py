"""Independent raw-row and separate-packet audit of synthetic exception F controls."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
def overlap(body):
    xs=[p[0] for p in body];ys=[p[1] for p in body]
    return max(0,min(max(xs),20)-max(min(xs),-15))*max(0,min(max(ys),-3)-max(min(ys),-5))

def main():
    summary=read(HERE/'exception-f-source-summary.json')
    assert summary['cases']==2 and summary['candidates']==8
    assert summary['original_native_capture_executed'] is False
    pairs={}
    for item in summary['results']:
        folder=(HERE/item['receipt']).parent
        assert sha(folder/'receipt.json')==item['receipt_sha256']
        receipt=read(folder/'receipt.json')
        for name,digest in receipt['hashes'].items():assert sha(folder/name)==digest,name
        packet=read(folder/'incident-packet.json');p=read(folder/'construction.json')
        measurement=read(folder/'measurement.json');trigger=read(folder/'trigger-measurement.json')
        source=[json.loads(line) for line in (folder/'source-rows.jsonl').read_text().splitlines()]
        assert len(source)==480
        assert packet['provenance']=='independent_synthetic_dispatch_fixture'
        assert packet['incident_id']=='fixture-incident-001'
        if item['state']=='emergency':
            assert packet['event_kind']=='roadway_medical_response'
            assert (packet['declared_start_frame'],packet['declared_end_frame'])==(100,240)
            assert packet['requested_vehicle_response'] is True
        else:
            assert packet['event_kind']=='routine_no_incident'
            assert (packet['declared_start_frame'],packet['declared_end_frame'])==(None,None)
            assert packet['requested_vehicle_response'] is False
        assert all(r['native_frame']==2000+i and r['time_s']==round(i/20,2) for i,r in enumerate(source))
        assert all(r['incident_id']==(packet['incident_id'] if r['incident_active'] else None) for r in source)
        assert all(r['bicycle_lane_body_occupied']==(overlap(r['ego_body_xy'])>0) for r in source)
        active=sum(r['incident_active'] for r in source)
        occupied=sum(r['bicycle_lane_body_occupied'] for r in source)
        joined=sum(r['incident_active'] and r['bicycle_lane_body_occupied'] for r in source)
        expected=(140,70,70) if item['state']=='emergency' else (0,0,0)
        assert (active,occupied,joined)==expected
        assert (measurement['incident_active_frames'],measurement['occupied_frames'],
                measurement['incident_occupied_frames'])==expected
        assert trigger['incident_observation_frames']==(0 if item['state']=='routine' else
            (120 if item['candidate_id']=='fallback1' else 80))
        assert trigger['response_lead_frames']==(35 if item['candidate_id']=='fallback2' else 20)
        assert trigger['scripted_reference_visible_fraction']==(1.0 if item['candidate_id']=='fallback3' else .887324)
        assert trigger['original_camera_pixels_verified'] is False
        negatives=read(folder/'negative-receipts.json')
        assert {n['kind'] for n in negatives}=={'incident_provenance','incident_interval',
            'incident_join','body_path','frame_identity'}
        assert all(n['rejected'] for n in negatives)
        pairs[item['state'],item['candidate_id']]=source
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        a=pairs['emergency',candidate];b=pairs['routine',candidate]
        assert all(x['native_frame']==y['native_frame'] and x['time_s']==y['time_s']
            and x['ego_center_xy'][0]==y['ego_center_xy'][0]
            and x['scripted_reference_visible']==y['scripted_reference_visible']
            for x,y in zip(a,b))
    result={'format':'c10052-exception-f-independent-source-audit-v1','passed':True,
            'positive_sources':8,'controlled_emergency_routine_pairs':4,'negative_rejections':40,
            'original_native_emergency_verified':False,'legal_exception_verified':False,
            'selected':False,'accepted':False}
    path=HERE/'exception-f-independent-audit.json'
    path.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
