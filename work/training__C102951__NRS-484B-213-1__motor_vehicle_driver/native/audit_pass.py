"""Independently recompute three synthetic hill-crest passing probes."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
DISTANCES=(70,120,170)
MUTATIONS=('source_hash','time_join','no_return','wrong_oncoming_side',
           'missing_sightline','road_direction')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    proof_path=HERE/'pass-proof.json';proof=json.loads(proof_path.read_text())
    root=HERE.parent.parent.parent
    if (proof['format']!='c102951-saved-pass-cpu-proof-v1' or
            proof['assignment_id']!=HERE.parent.name or
            proof['assignment_sha256']!=sha(root/'inputs'/HERE.parent.name/'assignment.json') or
            proof['case_plan_sha256']!=sha(HERE.parent/'case-plan.json') or
            proof['processor_sha256']!=sha(HERE/'measure_pass.py') or
            proof['original_native_observed'] or proof['delivery_ready'] or
            proof['safe_distance_judgment'] is not None):
        raise ValueError('Pass proof source identity differs')
    positives={row['requested_clear_oncoming_distance_m']:row['measurement'] for row in proof['positives']}
    negatives={(row['distance_m'],row['mutation']) for row in proof['negatives'] if row['rejected'] is True}
    if set(positives)!=set(DISTANCES) or negatives!={(d,m) for d in DISTANCES for m in MUTATIONS}:
        raise ValueError('Pass proof coverage differs')
    total=0;events={}
    for distance in DISTANCES:
        folder=HERE/'saved-fixtures'/str(distance)
        road_path=folder/'road-readback.json';actor_path=folder/'native-observed.jsonl'
        road=json.loads(road_path.read_text())
        if road!={'format':'c102951-road-readback-v1','lane_count':2,'travel_directions':2,
                  'centerline_y_m':0,'crest_profile':'authored_synthetic_probe',
                  'highway_status_reviewed':False,'source_kind':'synthetic_cpu'}:
            raise ValueError('Pass road readback differs')
        rows=[json.loads(line) for line in actor_path.read_text().splitlines()]
        if len(rows)!=480:raise ValueError('Pass actor row count differs')
        left=[];full=[];abreast=[];returned=[];gaps=[];eyes=[]
        passed=False
        for i,row in enumerate(rows):
            total+=1
            if (row['frame']!=i or row['native_frame']!=1000+i or
                    abs(row['time_s']-.05-i/20)>1e-4 or
                    row['source_kind']!='synthetic_cpu' or row['ego_blueprint']!='vehicle.tesla.model3' or
                    row['ego_speed_mps']!=16 or row['overtaken_speed_mps']!=8 or
                    row['oncoming_speed_mps']!=12 or not row['sightline_visible'] or
                    row['driver_eye_clear_m']!=distance or
                    abs(row['ego_x_m']-.8*i)>1e-4 or
                    abs(row['overtaken_x_m']-(30+.4*i))>1e-4):
                raise ValueError('Independent saved pass trace differs')
            if row['ego_y_m']+.9>0:
                left.append(i);eyes.append(row['driver_eye_clear_m'])
                if row['ego_y_m']-.9>0:full.append(i)
            if left and row['ego_x_m']+2.2>=row['overtaken_x_m']-2.2 and row['ego_x_m']-2.2<=row['overtaken_x_m']+2.2:
                abreast.append(i)
            if left and row['ego_x_m']-2.2>row['overtaken_x_m']+2.2:passed=True
            if passed and row['ego_y_m']+.9<=0:returned.append(i)
            if left and not returned:gaps.append((i,row['oncoming_x_m']-row['ego_x_m']-4.4))
        if not left or not full or not abreast or not returned:raise ValueError('Pass event absent')
        metric=positives[distance]
        expected={'format':'c102951-saved-pass-measurement-v1','source_kind':'synthetic_cpu',
                  'frames':480,'first_left_of_center_frame':left[0],
                  'first_full_left_frame':full[0],'first_abreast_frame':abreast[0],
                  'first_return_after_pass_frame':returned[0],
                  'left_of_center_frames':len(left),
                  'entry_oncoming_body_gap_m':round(rows[left[0]]['oncoming_x_m']-rows[left[0]]['ego_x_m']-4.4,3),
                  'minimum_pre_return_oncoming_body_gap_m':round(min(value for _,value in gaps),3),
                  'first_nonpositive_pre_return_oncoming_gap_frame':next((i for i,value in gaps if round(value,3)<=0),None),
                  'minimum_left_phase_driver_eye_clear_m':round(min(eyes),3),
                  'all_left_phase_sightline_flags_visible':True,
                  'highway_status_reviewed':False,'safe_distance_judgment':None,
                  'interference_judgment':None,'legal_verdict':None,
                  'source_hashes':{'native-observed.jsonl':sha(actor_path),'road-readback.json':sha(road_path)}}
        if metric!=expected or expected['entry_oncoming_body_gap_m']!=distance:
            differences={key:(metric.get(key),value) for key,value in expected.items()
                         if metric.get(key)!=value}
            raise ValueError('Independent saved pass measurement differs: '+str(differences))
        events[str(distance)]={'entry':left[0],'abreast':abreast[0],
                               'return':returned[0],
                               'first_nonpositive_gap':expected['first_nonpositive_pre_return_oncoming_gap_frame']}
    if total!=1440:raise ValueError('Pass audit row coverage differs')
    result={'format':'c102951-independent-saved-pass-audit-v1',
            'probe_count':3,'negative_count':18,'saved_rows_checked':total,
            'events':events,'proof_sha256':sha(proof_path),
            'original_native_observed':False,'delivery_ready':False}
    (HERE/'pass-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
