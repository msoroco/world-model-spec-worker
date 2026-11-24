"""Independent paired following-gap audit over retained source-shaped rows."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition,message):
    if not condition:raise ValueError(message)


def audit(negative=False):
    manifest=json.loads((ROOT/'execution-manifest.json').read_text())
    plan=json.loads((ROOT/'case-plan.json').read_text())
    comparison=plan['comparisons'][0]
    require(comparison['deliberate_differences']==['realized_following_gap'],'Comparison variable changed')
    records=[]
    for suffix, expected in [('condition_a',10.0),('condition_b',25.0)]:
        entry=next(e for e in manifest['cases'] if e['case_id'].endswith(suffix))
        require(entry['case_id'] in comparison['case_ids'],'Case omitted from controlled comparison')
        fixture=ROOT/'current-fixture'/suffix
        original=fixture/'native_samples.jsonl'
        rows=[json.loads(line) for line in original.read_text().splitlines()]
        require(len(rows)==900,'Full 900-frame source interval required')
        receipt=ROOT/entry['compatibility']['receipt']
        saved=ROOT/entry['saved_processing']['receipt']
        c=json.loads(receipt.read_text());s=json.loads(saved.read_text())
        require(sha(receipt)==entry['compatibility']['sha256'] and c['passed'] is True,'Selected compatibility receipt changed')
        require(sha(saved)==entry['saved_processing']['sha256'] and s['passed'] is True,'Selected saved receipt changed')
        require(c['construction_sha256']==entry['construction_sha256'],'Selected construction/compatibility mismatch')
        require(c['fixture_recipe_sha256']==sha(ROOT/'current-fixture'/(suffix+'-recipe.json')),'Selected fixture changed')
        require(s['recorded_only'] is True and s['originals_preserved'] is True,'Saved source lifecycle incomplete')
        require(s['timestamp_joins']['passed'] is True and s['timestamp_joins']['frames']==900,'Saved time join incomplete')
        require(s['final_video_checks']['passed'] is True and s['final_video_checks']['frames']==900,'Full saved final-video decode incomplete')
        require(s['physical_acceptance_claimed'] is False and s['legal_acceptance_claimed'] is False,'Synthetic proof overstated')
        gaps=[]
        for row in rows:
            ego,lead=row['ego'],row['lead']
            require((ego['native_road_id'],ego['native_lane_id'])==(lead['native_road_id'],lead['native_lane_id']),'Lead left ego lane')
            gaps.append(min(p[0] for p in lead['native_body_xy_m'])-max(p[0] for p in ego['native_body_xy_m']))
        require(max(abs(g-expected) for g in gaps)<1e-7,'Synthetic measured bumper gap differs')
        records.append((rows,{'case_id':entry['case_id'],'native_samples_sha256':sha(original),
                              'compatibility_sha256':sha(receipt),'saved_processing_sha256':sha(saved),
                              'synthetic_bumper_gap_m':expected}))
    a,b=records[0][0],records[1][0]
    if negative:
        b[400]['lead']['speed_mps']+=1.0
    for left,right in zip(a,b):
        require(left['native_frame']==right['native_frame'] and left['time_s']==right['time_s'],'Paired frame/time changed')
        require(left['ego']==right['ego'],'Paired ego body or motion changed')
        for key in ('native_road_id','native_lane_id','native_forward_xy','speed_mps'):
            require(left['lead'][key]==right['lead'][key],'Paired lead lane or motion changed: '+key)
        for p,q in zip(left['lead']['native_body_xy_m'],right['lead']['native_body_xy_m']):
            require(abs(q[0]-p[0]-15.0)<1e-8 and abs(q[1]-p[1])<1e-8,'Only declared 15 m lead-body shift allowed')
    return {'format':'worker-selected-comparison-audit','comparison_id':comparison['comparison_id'],
            'case_ids':comparison['case_ids'],'cases':[r[1] for r in records],
            'frames_per_case':900,'fixed_ego_context_and_lead_motion':True,
            'declared_difference':'realized_following_gap','synthetic_lead_body_shift_m':15.0,
            'physical_acceptance_claimed':False,'legal_verdict_claimed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--negative',action='store_true')
    args=parser.parse_args()
    result=audit(args.negative)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,sort_keys=True))
