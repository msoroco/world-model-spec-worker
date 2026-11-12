"""Saved-only bus Walk analysis from retained raw rows and source videos."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from measure_walk import analyze, read_rows, require
from physical_walk_audit import audit_original as audit_original_physical

CAMERAS=('overview','approach','reference_corner','driver_reference')
CHANNELS=('dev.pedestrian_signal','st.crosswalk','ru.pedestrian','rel.occupies',
          'drv.yields_to','kin.velocity','native_body_pose_control','camera_frame_join')


def source(folder,name):
    path=folder/name
    require(path.is_file(),'Missing required source: '+name)
    return path


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def joined_sources(attempt,count):
    trace=read_rows(source(attempt,'trace.jsonl'))
    evidence=read_rows(source(attempt,'capture/evidence.jsonl'))
    mapping=read_rows(source(attempt,'video_frames.jsonl'))
    native=read_rows(source(attempt,'native_samples.jsonl'))
    body=read_rows(source(attempt,'body_history.jsonl'))
    require(all(len(rows)==count for rows in (trace,evidence,mapping,native,body)),
            'Saved source frame counts differ')
    prior=-1
    for i,(t,e,m,n,b) in enumerate(zip(trace,evidence,mapping,native,body)):
        frame=m.get('native_frame');time=m.get('time_s')
        require(type(frame) is int and frame>prior and m.get('video_frame')==i and
                type(time) in (float,int) and math.isfinite(time),
                'Original video/Native frame mapping differs')
        prior=frame
        require(t.get('frame')==e.get('original_frame')==n.get('native_frame')==b.get('frame')==frame and
                all(abs(v-time)<1e-4 for v in
                    (t['time_s'],e['recording_time_s'],n['time_s'],b['time_s'])),
                'Original Native frame/time join differs')
        captured={(round(v[0],5),round(v[1],5)) for v in e['ego']['body_vertices_m']}
        bus={(round(v[0],5),round(v[1],5)) for v in n['bus_body_xy_m']}
        history={(round(v[0],5),round(v[1],5)) for v in b['bus_body_xy_m']}
        pedestrian={(round(v[0],5),round(v[1],5)) for v in n['pedestrian_body_xy_m']}
        ped_history={(round(v[0],5),round(v[1],5)) for v in b['pedestrian_body_xy_m']}
        require(captured==bus==history and pedestrian==ped_history and len(bus)==len(pedestrian)==4,
                'Original bus/pedestrian full body differs')
        require(abs(t['speed_mps']-n['bus_speed_mps'])<1e-4 and
                abs(e['ego']['speed_mps']-n['bus_speed_mps'])<1e-4,
                'Original bus speed source differs')
    capture=json.loads(source(attempt,'capture/manifest.json').read_text())
    require(capture.get('extraction_confirmed') is True and capture.get('frames')==count,
            'Capture extraction incomplete')
    synthetic=capture.get('synthetic_diagnostic') is True
    geometry=json.loads(source(attempt,'road_geometry.json').read_text())
    require((geometry.get('synthetic_diagnostic') is True)==synthetic,
            'Saved source provenance markers disagree')
    if synthetic:
        require(all(n.get('speed_provenance')=='synthetic_native_sample' and
                    t.get('speed_provenance')=='synthetic_native_sample' and
                    e.get('ego',{}).get('speed_provenance')=='synthetic_native_sample'
                    for n,t,e in zip(native,trace,evidence)),
                'Synthetic speed must retain diagnostic provenance')
    else:
        require(all(n.get('speed_provenance')=='native_measured' for n in native),
                'Original Native measured speed source absent')
    hashes={name:sha(source(attempt,name)) for name in
            ('trace.jsonl','capture/evidence.jsonl','video_frames.jsonl',
             'native_samples.jsonl','body_history.jsonl','capture/manifest.json')}
    return native,mapping,geometry,synthetic,{'frames':count,'source_sha256':hashes,
                                            'first_native_frame':mapping[0]['native_frame'],
                                            'last_native_frame':mapping[-1]['native_frame']}


def video_frames(path):
    completed=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=nb_read_frames','-of','default=noprint_wrappers=1:nokey=1',
        str(path)],capture_output=True,text=True,timeout=120)
    require(completed.returncode==0 and completed.stdout.strip().isdigit(),
            'Source video decode failed: '+path.name)
    return int(completed.stdout.strip())


def derive_channels(attempt,config,native,mapping,geometry,review=None):
    declared={row['name'] for row in config['recording_description']['channels']}
    require(declared==set(CHANNELS),'Declared channels differ from raw Walk derivation')
    output={name:[] for name in CHANNELS}
    for index,(sample,frame) in enumerate(zip(native,mapping)):
        observed=review['observations'][index] if review is not None else None
        display=observed['display'] if observed is not None else sample['walk_signal_display_observed']
        facing=observed['pedestrian_facing_signal'] if observed is not None else sample['pedestrian_facing_signal']
        pedestrian=sample['pedestrian_body_xy_m'];bus=sample['bus_body_xy_m']
        strip=(0,3.5,-12,-10)
        def overlaps(body):
            return min(p[0] for p in body)<=strip[1] and max(p[0] for p in body)>=strip[0] and \
                   min(p[1] for p in body)<=strip[3] and max(p[1] for p in body)>=strip[2]
        ped_inside=overlaps(pedestrian);bus_inside=overlaps(bus)
        values={
            'dev.pedestrian_signal':{'display':display,
                'actor_id':sample['walk_signal_actor_id'],
                'display_source':'independent_original_pixel_review' if observed is not None
                    else sample.get('display_source','synthetic_native_sample')},
            'st.crosswalk':{'y_range_m':geometry['crosswalk_y_range_m'],
                            'bus_lane_x_range_m':geometry['bus_lane_x_range_m']},
            'ru.pedestrian':{'actor_id':sample['pedestrian_actor_id'],
                             'body_xy_m':pedestrian,'facing_signal':facing},
            'rel.occupies':{'pedestrian_conflict_strip':ped_inside,
                            'bus_conflict_strip':bus_inside},
            'drv.yields_to':{'simultaneous_conflict_strip':ped_inside and bus_inside and
                facing and display=='Walk',
                'legal_yield_verdict':None},
            'kin.velocity':sample['bus_speed_mps'],
            'native_body_pose_control':sample,
            'camera_frame_join':frame}
        for name,value in values.items():
            output[name].append(json.dumps({'time_s':frame['time_s'],'value':value},
                                           allow_nan=False)+'\n')
    folder=attempt/'channels';folder.mkdir(exist_ok=True)
    for name,values in output.items():
        (folder/(name+'.jsonl')).write_text(''.join(values))


def measure_signal_presence(measurement):
    return {'sampled_frames':measurement['frames'],
            'walk_display_frames':measurement['walk_display_frames'],
            'synthetic_diagnostic':measurement['synthetic_diagnostic']}


def measure_walk_crossing(measurement):
    return {'directed_pedestrian_conflict_frames':measurement['directed_pedestrian_conflict_frames'],
            'first_directed_pedestrian_conflict_frame':measurement['first_directed_pedestrian_conflict_frame'],
            'synthetic_diagnostic':measurement['synthetic_diagnostic']}


def measure_bus_yield(measurement):
    return {'bus_conflict_frames':measurement['bus_conflict_frames'],
            'simultaneous_conflict_frames':measurement['simultaneous_conflict_frames'],
            'first_simultaneous_conflict_frame':measurement['first_simultaneous_conflict_frame'],
            'synthetic_diagnostic':measurement['synthetic_diagnostic']}


def finalize(attempt,output):
    attempt=Path(attempt).resolve();output=Path(output).resolve()
    require(not output.exists() and not (attempt/'result.json').exists(),
            'Retain prior finalization; use a fresh attempt')
    config=json.loads(source(attempt,'config.json').read_text())
    count=config['rate_hz']*config['duration_s']
    require(count==480,'Exact 480-frame Walk capture contract differs')
    native,mapping,geometry,synthetic,joins=joined_sources(attempt,count)
    original_physical=None
    review=None
    if not synthetic:
        review_path=source(attempt,'official-walk-review.json')
        original_physical=audit_original_physical(attempt,config['case_suffix'],review_path)
        review=json.loads(review_path.read_text())
    measurement=analyze(attempt,review)
    counts={name:video_frames(source(attempt,name+'.mkv')) for name in CAMERAS}
    require(all(value==count for value in counts.values()),
            'Original source video frame count differs')
    derive_channels(attempt,config,native,mapping,geometry,review)
    expected=config['case_suffix']=='reference'
    no_simultaneous=measurement['simultaneous_conflict_frames']==0
    matched=no_simultaneous==expected and measurement['directed_pedestrian_conflict_frames']>0
    completed=original_physical is not None and \
        original_physical['physical_checks']['maneuver']['status']=='met' and matched
    recording=[{'name':row['name'],'unit':row['unit'],
                'reference':'channels/'+row['name']+'.jsonl'}
               for row in config['recording_description']['channels']]
    result={'case_id':config['case_id'],
        'measured_values':{'walk_crossing':measurement},
        'target_checks':[{'target':'sampled bus/pedestrian conflict strip under directed Walk',
            'requested':expected,'measured':no_simultaneous,
            'method':'source-hashed saved full-body and Walk frame join',
            'tolerance':0,'matched':matched,'physical_cause_confirmed':False,
            'cause_evidence':['native_samples.jsonl','video_frames.jsonl','road_geometry.json']+
                (['official-walk-review.json'] if original_physical else [])}],
        'setup_confirmed':original_physical is not None,
        'behavior_attempted':original_physical is not None,
        'maneuver_completed':completed,
        'termination_reason':'full original duration retained',
        'physical_failure_flags':
            (['official_Walk_pixels_governance_and_bus_control_need_independent_review'] if synthetic else [])+
            ([] if completed or synthetic else ['controlled_crossing_behavior_unconfirmed'])+
            ([] if matched else ['sampled_target_unmatched']),
        'trace_reference':'trace.jsonl','video_references':[name+'.mkv' for name in CAMERAS],
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':config['recording_description'],
        'recording_evidence':recording,
        'realized_observables':{'first_bus_conflict_frame':{'value':measurement['first_bus_conflict_frame'],
            'unit':'frame','method':'saved sampled full-body crosswalk overlap',
            'time_window':'entire original 24 s attempt','statistic':'first',
            'reference':'native_samples.jsonl'}},
        'provenance_kind':'synthetic_local_diagnostic' if synthetic else 'native',
        'diagnostic_fixture':synthetic,'accepted':False,'legal_verdict_claimed':False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report={'format':'c111256-saved-analysis-v1','case_id':config['case_id'],
            'candidate_id':config['candidate_id'],
            'measurements':{
                key:{'value':method(measurement),'method':method.__name__,
                     'sources':measurement['source_sha256']}
                for key,method in (
                    ('signal_presence_observation',measure_signal_presence),
                    ('walk_crossing_observation',measure_walk_crossing),
                    ('bus_yield_observation',measure_bus_yield))},
            'original_joins':joins,'video_frames':counts,
            'provenance_kind':result['provenance_kind'],
            'physical_acceptance_claimed':False,'legal_verdict_claimed':False,
            'original_physical_audit':original_physical,
            'scope':'synthetic diagnostic' if synthetic else 'saved original Native sources pending independent audit'}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    with (attempt/'result.json').open('x') as stream:
        json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output),sort_keys=True))


if __name__=='__main__':main()
