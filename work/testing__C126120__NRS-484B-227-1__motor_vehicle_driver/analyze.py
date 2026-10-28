"""Audit actual full-body median passage, surface rays, and reverse movement."""
import argparse
from native_finalize import finalize
import hashlib
import json
import sys
from pathlib import Path

from scenario import route

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO/'runtime/main-pipeline-v1/scenario_pipeline'))
from worker_exchange.media import audit as audit_source_video


def source_audits(attempt, cfg, rows):
    mapping_path = attempt/'video_frames.jsonl'
    mapping = [json.loads(x) for x in mapping_path.read_text().splitlines()]
    trace = [json.loads(x) for x in (attempt/'trace.jsonl').read_text().splitlines()]
    evidence = [json.loads(x) for x in (attempt/'capture/evidence.jsonl').read_text().splitlines()]
    count = len(rows)
    if not count or len(mapping)!=count or len(trace)!=count or len(evidence)!=count:
        raise ValueError('Original sample/trace/evidence/video frame counts differ')
    for i, (sample, frame, state, event) in enumerate(zip(rows,mapping,trace,evidence)):
        if (frame['video_frame']!=i or frame['native_frame']!=sample['frame'] or frame.get('carla_frame')!=sample['frame'] or
                state['frame']!=sample['frame'] or event['original_frame']!=sample['frame'] or
                abs(frame['time_s']-sample['time_s'])>1e-6):
            raise ValueError('Original source frame/time join differs')
    for channel in cfg['case']['recording_description']['channels']:
        path=attempt/'channels'/(channel['name']+'.jsonl')
        values=[json.loads(x) for x in path.read_text().splitlines()]
        if len(values)!=count or any(abs(v['time_s']-r['time_s'])>1e-6 for v,r in zip(values,rows)):
            raise ValueError('Mandatory channel count/time join differs: '+channel['name'])
    mapping_sha=hashlib.sha256(mapping_path.read_bytes()).hexdigest()
    outputs=[]
    diagnostic = (attempt/'fixture-provenance.json').is_file() and (attempt/'raw.mkv').is_file() and not (attempt/'view0.mkv').exists()
    camera_specs = [(0, cfg['cameras'][0])] if diagnostic else list(enumerate(cfg['cameras']))
    for i,spec in camera_specs:
        video=attempt/'raw.mkv' if diagnostic else attempt/('view%d.mkv'%i)
        receipt=attempt/('view%d.source-audit.json'%i)
        result=audit_source_video(video,count,mapping_sha256=mapping_sha,receipt=receipt)
        if not diagnostic and result['dimensions']!=[spec['width'],spec['height']]:
            raise ValueError('Original camera dimensions differ')
        outputs.append({'video':video.name,'receipt':receipt.name,
                        'video_sha256':result['video_sha256'],'decoded_frames':result['frames']})
    return outputs


def top_z(ray):
    return max((hit['location_m'][2] for hit in ray['hits']),default=None)


def assess(attempt):
    attempt=Path(attempt)
    cfg=json.loads((attempt/'config.json').read_text())
    setup=json.loads((attempt/'native-setup.json').read_text())
    rows=[json.loads(x) for x in (attempt/'physical_samples.jsonl').read_text().splitlines()]
    audits=source_audits(attempt,cfg,rows)
    rays={tuple(r['xy_m']):r for r in setup['native_surface_rays']}
    west_top=top_z(rays[(150,10)])
    opening_top=top_z(rays[(205,10)])
    east_top=top_z(rays[(250,10)])
    physical_barrier_confirmed=all(v is not None for v in (west_top,opening_top,east_top)) and west_top-opening_top>.5 and east_top-opening_top>.5
    median=[r for r in rows if r['median_status']['median_overlap']]
    intact=[r for r in median if r['median_status']['intact_divider_overlap']]
    through_opening=bool(median) and all(r['median_status']['wholly_within_opening_x'] for r in median)
    reverse_requested=any(r['reverse_ticks']>0 for r in rows)
    actual_reverse=any(b['position_m'][0]<a['position_m'][0]-.02
                       for a,b in zip(rows,rows[1:]) if b['reverse_ticks']>0 and b['position_m'][1]<0)
    collisions=rows[-1]['collision_events'] if rows else []
    completed=bool(rows and rows[-1]['route_index']>=len(route(cfg['case']))-2)
    branch=cfg['case']['variable_assignments']['test_branch']['value']
    branch_observed=(bool(intact) and bool(collisions) if branch=='u_turn_divider' else through_opening)
    if branch=='u_turn_opening_multiple':branch_observed=branch_observed and actual_reverse
    terminal_observed=bool(collisions) if branch=='u_turn_divider' else completed
    decision='inspect_native_barrier_pixels_and_footprints' if physical_barrier_confirmed and branch_observed and terminal_observed else 'repair_same_frozen_case'
    return {'format':'median-opening-capability-v1','case_id':cfg['selected_case_id'],'branch':branch,
            'native_surface_top_z_m':{'intact_west':west_top,'opening':opening_top,'intact_east':east_top},
            'physical_barrier_height_difference_confirmed':physical_barrier_confirmed,
            'median_sample_count':len(median),'intact_overlap_sample_count':len(intact),
            'all_median_samples_within_opening':through_opening,
            'reverse_requested':reverse_requested,'actual_reverse_observed':actual_reverse,
            'collision_events':collisions,'route_completed':completed,
            'physical_failure_observed':bool(collisions),
            'capability_terminal_observed':terminal_observed,
            'legal_conclusion':None,
            'original_source_audits':audits,
            'branch_physical_measurement_observed':branch_observed,
            'public_authority_established':None,
            'decision':decision,
            'follow_up_configuration':{'source':'config.json','case_id':cfg['selected_case_id'],
                'preserve_branch_and_opening_bounds':True,
                'if_barrier_unconfirmed':'survey native surface/collision and rebuild physical divider without changing frozen case'},
            'physical_acceptance':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();report = assess(a.attempt)
    Path(a.output).write_text(json.dumps(report, indent=2) + '\n')
    finalize(a.attempt, report)
