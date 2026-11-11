"""Saved original-source C10316 finalization without a practicability verdict."""
import json
import math
from pathlib import Path
import subprocess

from measure_crosswalk import measure,sha


def required(folder,name):
    path=Path(folder)/name
    if not path.is_file():raise ValueError('Missing required source: '+name)
    return path


def rows(folder,name):
    return [json.loads(line) for line in required(folder,name).read_text().splitlines() if line.strip()]


def crosswalk_passage(folder):
    folder=Path(folder)
    return measure(folder/'native_samples.jsonl',folder/'crosswalk-context.json')


def analysis_report(folder,contract=None):
    folder=Path(folder)
    config=json.loads(required(folder,'config.json').read_text())
    if contract is None:
        contract={'case_id':config['case_id'],
                  'requirements':[{'output_key':'right_half_passage','method':'crosswalk_passage',
                                   'inputs':['native_samples.jsonl','crosswalk-context.json']},
                                  {'output_key':'marked_crosswalk_passage','method':'crosswalk_passage',
                                   'inputs':['native_samples.jsonl','crosswalk-context.json']}]}
    observation=crosswalk_passage(folder)
    values={}
    for row in contract['requirements']:
        if row['method'] not in ('crosswalk_passage','measure'):
            raise ValueError('Unrecognized C10316 measurement method')
        values[row['output_key']]={'method':row['method'],'value':observation,
                                   'sources':{name:sha(required(folder,name)) for name in row['inputs']}}
    return {'format':'worker-analysis-report-v1','case_id':contract['case_id'],
            'measurements':values,'scope':'source_bound_crosswalk_half_without_practicability_verdict'}


def verify_original_joins(folder,count):
    names=('trace.jsonl','capture/evidence.jsonl','video_frames.jsonl',
           'native_samples.jsonl','capture/native/frames.jsonl')
    trace,evidence,mapping,samples,native=(rows(folder,name) for name in names)
    if any(len(source)!=count for source in (trace,evidence,mapping,samples,native)):
        raise ValueError('Original trace/evidence/Native/frame counts differ')
    previous_frame,previous_time=-1,-math.inf
    for index,(t,e,m,s,n) in enumerate(zip(trace,evidence,mapping,samples,native)):
        frame,time=m.get('native_frame'),m.get('time_s')
        if type(frame) is not int or type(time) not in (int,float) or frame<=previous_frame or time<=previous_time:
            raise ValueError('Original frame/time order invalid')
        if m.get('video_frame')!=index or m.get('carla_frame')!=frame:
            raise ValueError('Original camera frame mapping invalid')
        if any(item!=frame for item in (t.get('frame'),e.get('original_frame'),
                                       s.get('native_frame'),n.get('frame'))):
            raise ValueError('Original Native frame join differs')
        if any(abs(float(item)-time)>1e-4 for item in
               (t['time_s'],e['recording_time_s'],s['time_s'])):
            raise ValueError('Original Native timestamp join differs')
        evidence_body={(round(v[0],3),round(v[1],3)) for v in e['ego']['body_vertices_m']}
        sample_body={(round(v[0],3),round(v[1],3)) for v in s['pedestrian_footprint_xy_m']}
        if len(evidence_body)!=4 or evidence_body!=sample_body:
            raise ValueError('Original pedestrian footprint differs from captured evidence')
        previous_frame,previous_time=frame,time
    capture=json.loads(required(folder,'capture/manifest.json').read_text())
    if capture.get('extraction_confirmed') is not True or capture.get('frames')!=count:
        raise ValueError('Original capture extraction incomplete')
    return {'frames':count,'first_frame':mapping[0]['native_frame'],
            'last_frame':mapping[-1]['native_frame'],
            'source_hashes':{name:sha(Path(folder)/name) for name in names}}


def video_info(path):
    path=Path(path)
    if not path.is_file():raise ValueError('Missing required source: '+path.name)
    probe=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
                          '-show_entries','stream=width,height,nb_read_frames',
                          '-of','json',str(path)],text=True,stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,timeout=120)
    if probe.returncode:raise ValueError('Source video decode failed: '+path.name)
    streams=json.loads(probe.stdout).get('streams',[])
    if len(streams)!=1 or not str(streams[0].get('nb_read_frames','')).isdigit():
        raise ValueError('Source video frame count missing: '+path.name)
    return (int(streams[0]['nb_read_frames']),int(streams[0]['width']),int(streams[0]['height']))


def derive_channels(folder,config,count):
    """Rebuild derived observations from retained Native rows and frame mapping."""
    folder=Path(folder)
    samples=rows(folder,'native_samples.jsonl')
    mapping=rows(folder,'video_frames.jsonl')
    if len(samples)!=count or len(mapping)!=count:
        raise ValueError('Raw source counts differ before channel derivation')
    expected={'kin.position','kin.heading','rel.occupies',
              'native_pedestrian_pose','camera_frame_join'}
    declared={item['name'] for item in config['recording_description']['channels']}
    if declared!=expected:
        raise ValueError('Declared pedestrian channels differ from raw derivation')
    output={name:[] for name in expected}
    for sample,frame in zip(samples,mapping):
        if sample['native_frame']!=frame['native_frame'] or abs(sample['time_s']-frame['time_s'])>1e-4:
            raise ValueError('Channel source frame/time join differs')
        time=frame['time_s']
        values={
            'kin.position':sample['pedestrian_xy_m'],
            'kin.heading':sample['pedestrian_forward_xy'],
            'rel.occupies':{'crosswalk_id':sample['crosswalk_id'],
                            'original_footprint_xy_m':sample['pedestrian_footprint_xy_m']},
            'native_pedestrian_pose':sample,
            'camera_frame_join':{key:frame[key] for key in
                                 ('video_frame','native_frame','carla_frame','time_s')},
        }
        for name,value in values.items():
            output[name].append(json.dumps({'time_s':time,'value':value},allow_nan=False)+'\n')
    channels=folder/'channels';channels.mkdir(exist_ok=True)
    for name,lines in output.items():
        (channels/(name+'.jsonl')).write_text(''.join(lines))


def finalize(attempt,output):
    from worker_exchange.native_output import validate_result
    attempt,output=Path(attempt).resolve(),Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain original finalization; use a fresh attempt')
    config=json.loads(required(attempt,'config.json').read_text())
    count=config['duration_s']*config['rate_hz']
    if count!=240:raise ValueError('Full 12-second pedestrian window changed')
    joins=verify_original_joins(attempt,count)
    derive_channels(attempt,config,count)
    report=analysis_report(attempt)
    observed=report['measurements']['right_half_passage']['value']
    context=json.loads(required(attempt,'crosswalk-context.json').read_text())
    expected='right' if config['case_suffix']=='reference' else 'left'
    videos={}
    for camera in config['cameras']:
        name=camera['name']+'.mkv'
        info=video_info(attempt/name)
        if info!=(count,camera['width'],camera['height']):
            raise ValueError('Source camera frame count or dimensions differ: '+name)
        videos[name]={'frames':info[0],'width':info[1],'height':info[2]}
    evidence=[]
    for channel in config['recording_description']['channels']:
        ref='channels/'+channel['name']+'.jsonl'
        required(attempt,ref)
        evidence.append({'name':channel['name'],'unit':channel['unit'],'reference':ref})
    for item in config['recording_description']['context_inputs']:
        evidence.append({'name':item['name'],'unit':item['unit'],
                         'reference':'crosswalk-context.json'})
    measured=observed['observed_half']
    result={'case_id':config['case_id'],
            'measured_values':{'observed_crosswalk_half':measured,
                               'crosswalk_frames':observed['crosswalk_frames'],
                               'passage_duration_s':observed['passage_duration_s']},
            'target_checks':[{'target':'full-window crosswalk half','requested':expected,
                'measured':measured,'method':'original pedestrian footprints across joined Native frames',
                'tolerance':0,'matched':measured==expected,
                'physical_cause_confirmed':False,
                'cause_evidence':['native_samples.jsonl','crosswalk-context.json','trace.jsonl']}],
            'setup_confirmed':False,
            'behavior_attempted':context['source_kind']=='native_observation',
            'maneuver_completed':context['source_kind']=='native_observation' and measured==expected,
            'termination_reason':'full original source interval retained',
            'physical_failure_flags':['practicability_and_original_pixels_unverified'],
            'trace_reference':'trace.jsonl','video_references':list(videos),
            'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':config['recording_description'],
            'recording_evidence':evidence,
            'realized_observables':{'pedestrian_right_half_fraction':{
                'value':observed['crosswalk_half_counts']['right']/observed['crosswalk_frames'],
                'unit':'ratio',
                'method':'original four-vertex footprints within crosswalk geometry',
                'time_window':'entire original 12-second passage','statistic':'fraction of fully contained frames',
                'reference':'native_samples.jsonl'}},
            'provenance_kind':('synthetic_local_diagnostic' if context['source_kind']=='synthetic_scene_request'
                               else 'native_source_shape_unverified'),
            'accepted':False,'legal_verdict_claimed':False}
    validate_result(result)
    report.update(format='c10316-saved-crosswalk-analysis-v1',
                  candidate_id=config['candidate_id'],original_joins=joins,
                  video_frames=videos,
                  scope='saved original-source joins and video decode; no practicability or legal finding')
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (attempt/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return report


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output),allow_nan=False))
