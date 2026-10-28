"""Native measured capability decision, with frozen-case follow-up configuration."""
import argparse
import hashlib
import json
import pathlib
import statistics
import sys
for ancestor in pathlib.Path(__file__).resolve().parents:
    pipeline = ancestor / 'runtime/main-pipeline-v1/scenario_pipeline'
    if pipeline.is_dir():
        sys.path.insert(0, str(pipeline))
        break
from worker_exchange.media import audit


def assess(attempt):
    attempt=pathlib.Path(attempt)
    cfg=json.loads((attempt/'config.json').read_text())
    rows=[json.loads(line) for line in (attempt/'physical_samples.jsonl').read_text().splitlines()]
    if not rows:
        raise ValueError('No original physical samples')
    mapping=[json.loads(line) for line in (attempt/'video_frames.jsonl').read_text().splitlines()]
    if len(mapping)!=len(rows) or any(m['native_frame']!=r['frame'] or m['video_frame']!=i
        for i,(m,r) in enumerate(zip(mapping,rows))):
        raise ValueError('Original physical/video frame mapping differs')
    if any(b['time_s']<=a['time_s'] for a,b in zip(rows,rows[1:])):
        raise ValueError('Original physical samples are not time ordered')
    mapping_sha=hashlib.sha256((attempt/'video_frames.jsonl').read_bytes()).hexdigest()
    video_receipts=[]
    for i in range(4):
        video=attempt/('view%d.webm'%i)
        receipt=attempt/('view%d.source-decode.json'%i)
        video_receipts.append(audit(video,len(rows),mapping_sha256=mapping_sha,receipt=receipt))
    law=cfg['law_id']
    case=cfg['case']
    setup=json.loads((attempt/'native_setup.json').read_text())
    measurements={'sample_count':len(rows),'first_time_s':rows[0]['time_s'],'last_time_s':rows[-1]['time_s']}
    measurements['native_road_count']=len(set(setup['native_road_ids']))
    measurements['video_source_receipts']=[{'video_sha256':v['video_sha256'],
        'frames':v['frames'],'dimensions':v['dimensions']} for v in video_receipts]
    if law.endswith('400-2b'):
        exit_rows=[r for r in rows if r['position_m'][1]>11]
        measurements['exit_body_right_of_native_centerline']=bool(exit_rows) and all(
            all(v[0]>=0 for v in r['body_vertices_m']) for r in exit_rows)
    elif law.endswith('253'):
        overlap=[r for r in rows if abs(r['position_m'][0])<7 and abs(r['position_m'][1])<7]
        measurements['ego_intersection_samples']=len(overlap)
        measurements['opposing_intersection_samples']=sum(1 for r in rows for p in r['participants']
            if abs(p['position_m'][0])<7 and abs(p['position_m'][1])<7)
        measurements['ego_min_speed_near_junction_mps']=min((r['speed_mps'] for r in rows if -25<r['position_m'][0]<-8),default=None)
    elif law.endswith('223-1b'):
        measurements['lane_change_lateral_m']=rows[-1]['position_m'][1]-rows[0]['position_m'][1]
        measurements['indicator_bits_before_change']=[r['light_state_bits'] for r in rows if -26<r['position_m'][0]<-20]
    elif law.endswith('127-3'):
        gaps=[]
        for r in rows:
            if r['participants']:
                leader=r['participants'][0]
                gaps.append(min(v[0] for v in leader['body_vertices_m'])-max(v[0] for v in r['body_vertices_m']))
        measurements['measured_min_footprint_gap_m']=min(gaps) if gaps else None
        measurements['measured_mean_footprint_gap_m']=statistics.mean(gaps) if gaps else None
        entrant=[r['participants'][1] for r in rows if len(r['participants'])>1]
        measurements['entrant_present_original_frames']=len(entrant)
        measurements['entrant_final_lateral_m']=entrant[-1]['position_m'][1] if entrant else None
    else:
        measurements['native_stop_sign_count']=len(setup['stop_signs'])
        measurements['physical_crosswalk_tile_count']=len(setup['crosswalk_tiles'])
        near=[r for r in rows if -25<r['position_m'][0]<-8]
        measurements['minimum_speed_before_crosswalk_mps']=min((r['speed_mps'] for r in near),default=None)
        measurements['near_crosswalk_samples']=len(near)
    complete=rows[-1]['route_index']>=len(__import__('runner').route(cfg))-2
    measurements['route_completed']=complete
    follow=json.loads(json.dumps(cfg))
    follow['capability_follow_up']={'reason':'inspect original samples, native geometry and actual camera pixels',
                                   'same_frozen_case':case['case_id'],'preserve_requested_values':True,
                                   'adjustments_permitted_only_after_evidence_review':True}
    return {'format':'partition-01-capability-report-v1','case_id':case['case_id'],
            'measurements':measurements,'decision':'inspect_native_evidence' if complete else 'repair_controller_same_case',
            'physical_acceptance':False,'legal_verdict':None,'follow_up_config':follow}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();pathlib.Path(args.output).write_text(json.dumps(assess(args.attempt),indent=2)+'\n')
