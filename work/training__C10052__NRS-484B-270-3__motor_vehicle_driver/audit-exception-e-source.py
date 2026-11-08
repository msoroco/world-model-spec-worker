"""Independent officer packet, source response and lane-body audit."""
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
    summary=read(HERE/'exception-e-source-summary.json')
    assert summary['cases']==2 and summary['candidates']==8
    assert summary['original_native_capture_executed'] is False
    pairs={}
    for item in summary['results']:
        folder=(HERE/item['receipt']).parent
        receipt=read(folder/'receipt.json')
        assert sha(folder/'receipt.json')==item['receipt_sha256']
        assert all(sha(folder/name)==digest for name,digest in receipt['hashes'].items())
        state=item['state'];candidate=item['candidate_id'];directed=state=='directed'
        packet=read(folder/'officer-direction.json')
        assert packet['format']=='synthetic-police-direction-v1'
        assert packet['issuer']=='synthetic_traffic_officer_actor'
        assert packet['direction_id']=='fixture-direction-001'
        assert packet['active'] is directed
        assert (packet['officer_id'],packet['addressed_vehicle_id'],packet['command'])==(
            ('fixture-officer-12','fixture-driver-vehicle-17','enter_bicycle_lane')
            if directed else (None,None,None))
        assert (packet['start_frame'],packet['end_frame'])==((100,240) if directed else (None,None))
        source=[json.loads(line) for line in (folder/'source-rows.jsonl').read_text().splitlines()]
        assert len(source)==480
        for i,r in enumerate(source):
            active=directed and 100<=i<240
            occupied=directed and 120<=i<190
            assert r['native_frame']==3000+i and r['time_s']==round(i/20,2)
            assert r['vehicle_id']=='fixture-driver-vehicle-17'
            assert r['officer_id']==('fixture-officer-12' if active else None)
            assert r['direction_id']==('fixture-direction-001' if active else None)
            assert r['packet_command']==('enter_bicycle_lane' if active else None)
            assert r['direction_active'] is active
            assert r['driver_response']==('lane_enter' if occupied else 'lane_clear')
            assert r['bicycle_lane_body_occupied'] is occupied
            assert r['bicycle_lane_body_occupied']==(overlap(r['ego_body_xy'])>.001)
        active=sum(r['direction_active'] for r in source)
        occupied=sum(r['bicycle_lane_body_occupied'] for r in source)
        joined=sum(r['direction_active'] and r['bicycle_lane_body_occupied'] for r in source)
        assert (active,occupied,joined)==((140,70,70) if directed else (0,0,0))
        measurement=read(folder/'measurement.json')
        assert (measurement['direction_active_frames'],measurement['occupied_frames'],
                measurement['direction_response_frames'])==(active,occupied,joined)
        assert measurement['original_native_police_direction_verified'] is False
        assert measurement['legal_compliance_verified'] is False
        trigger=read(folder/'trigger-measurement.json')
        assert trigger['direction_observation_frames']==(
            0 if not directed else (120 if candidate=='fallback1' else 80))
        assert trigger['response_lead_frames']==(35 if candidate=='fallback2' else 20)
        assert trigger['scripted_reference_visible_fraction']==(
            1.0 if candidate=='fallback3' else .887324)
        assert trigger['original_camera_pixels_verified'] is False
        negatives=read(folder/'negative-receipts.json')
        assert {n['kind'] for n in negatives}=={'packet_issuer','packet_interval',
            'officer_identity','command','direction_join','driver_response',
            'body_path','frame_identity'}
        assert all(n['rejected'] for n in negatives)
        pairs[state,candidate]=source
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        a=pairs['directed',candidate];b=pairs['routine',candidate]
        assert all(x['native_frame']==y['native_frame'] and x['time_s']==y['time_s']
            and x['ego_center_xy'][0]==y['ego_center_xy'][0]
            and x['scripted_reference_visible']==y['scripted_reference_visible']
            for x,y in zip(a,b))
    result={'format':'c10052-exception-e-independent-source-audit-v1','passed':True,
        'positive_sources':8,'controlled_directed_routine_pairs':4,'negative_rejections':64,
        'original_native_police_direction_verified':False,'legal_compliance_verified':False,
        'selected':False,'accepted':False}
    path=HERE/'exception-e-independent-audit.json'
    path.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
