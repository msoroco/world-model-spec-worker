"""Independent duty packet, actor identity and body-overlap source audit."""
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
    summary=read(HERE/'exception-d-source-summary.json')
    assert summary['cases']==2 and summary['candidates']==8
    assert summary['original_native_capture_executed'] is False
    pairs={}
    for item in summary['results']:
        folder=(HERE/item['receipt']).parent
        receipt=read(folder/'receipt.json')
        assert sha(folder/'receipt.json')==item['receipt_sha256']
        assert all(sha(folder/name)==digest for name,digest in receipt['hashes'].items())
        state=item['state'];candidate=item['candidate_id']
        packet=read(folder/'duty-assignment.json')
        assert packet['format']=='synthetic-duty-assignment-v1'
        assert packet['issuer']=='synthetic_public_works_dispatch'
        assert packet['assignment_id']=='fixture-duty-001'
        assert packet['active'] is (state=='duty')
        assert packet['task']==('bicycle_facility_surface_inspection' if state=='duty' else 'none')
        assert (packet['authorized_vehicle_id'],packet['authorized_operator_id'])==(
            ('fixture-service-vehicle-17','fixture-operator-04') if state=='duty' else (None,None))
        assert (packet['start_frame'],packet['end_frame'])==(
            (100,240) if state=='duty' else (None,None))
        source=[json.loads(line) for line in (folder/'source-rows.jsonl').read_text().splitlines()]
        assert len(source)==480
        assert all(r['native_frame']==3000+i and r['time_s']==round(i/20,2) for i,r in enumerate(source))
        assert all((r['vehicle_id'],r['operator_id'])==
            ('fixture-service-vehicle-17','fixture-operator-04') for r in source)
        assert all(r['assignment_id']==('fixture-duty-001' if r['duty_active'] else None)
                   for r in source)
        assert all(r['bicycle_lane_body_occupied']==(overlap(r['ego_body_xy'])>.001)
                   for r in source)
        active=sum(r['duty_active'] for r in source)
        occupied=sum(r['bicycle_lane_body_occupied'] for r in source)
        joined=sum(r['duty_active'] and r['bicycle_lane_body_occupied'] for r in source)
        assert (active,occupied,joined)==((140,70,70) if state=='duty' else (0,0,0))
        measurement=read(folder/'measurement.json')
        assert (measurement['duty_active_frames'],measurement['occupied_frames'],
                measurement['duty_occupied_frames'])==(active,occupied,joined)
        assert measurement['original_native_official_duty_verified'] is False
        trigger=read(folder/'trigger-measurement.json')
        assert trigger['duty_observation_frames']==(
            0 if state=='routine' else (120 if candidate=='fallback1' else 80))
        assert trigger['response_lead_frames']==(35 if candidate=='fallback2' else 20)
        assert trigger['scripted_reference_visible_fraction']==(
            1.0 if candidate=='fallback3' else .887324)
        assert trigger['original_camera_pixels_verified'] is False
        negative=read(folder/'negative-receipts.json')
        assert {n['kind'] for n in negative}=={'assignment_issuer','assignment_interval',
            'assignment_join','actor_identity','body_path','frame_identity'}
        assert all(n['rejected'] for n in negative)
        pairs[state,candidate]=source
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        a=pairs['duty',candidate];b=pairs['routine',candidate]
        assert all(x['native_frame']==y['native_frame'] and x['time_s']==y['time_s']
            and x['ego_center_xy'][0]==y['ego_center_xy'][0]
            and x['scripted_reference_visible']==y['scripted_reference_visible']
            for x,y in zip(a,b))
    result={'format':'c10052-exception-d-independent-source-audit-v1','passed':True,
        'positive_sources':8,'controlled_duty_routine_pairs':4,'negative_rejections':48,
        'original_native_official_duty_verified':False,'legal_exception_verified':False,
        'selected':False,'accepted':False}
    path=HERE/'exception-d-independent-audit.json'
    path.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
