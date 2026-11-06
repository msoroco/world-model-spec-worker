"""Saved-only 480-frame truck-following analysis; never accepts a recording."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from measure_gap import measure as measure_single_lane

FRAMES=480
VIDEOS=('overview.mkv','ego_forward.mkv','lead_gap.mkv','crest_context.mkv')
ROWS=('native_samples.jsonl','trace.jsonl','capture/evidence.jsonl','video_frames.jsonl')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(root,name):
    path=root/name
    if not path.is_file():raise ValueError('Missing required source: '+name)
    return path


def rows(path):return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def frames(path):
    result=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=nb_read_frames','-of','default=noprint_wrappers=1:nokey=1',
        str(path)],capture_output=True,text=True,timeout=120)
    if result.returncode or not result.stdout.strip().isdigit():
        raise ValueError('Source video decode failed: '+path.name)
    return int(result.stdout.strip())


def measure(source_dir,suffix):
    """Case-specific source measurement exposed to the pinned contract validator."""
    if suffix in ('conditions_steady','conditions_lead_brake'):
        from conditions_qualifier import measure as measure_conditions
        return measure_conditions(source_dir)
    if suffix in ('passing_overtake','passing_hold'):
        from passing_carveout import measure as measure_passing
        return measure_passing(source_dir)
    if suffix=='two_lane_exception':
        from two_lane_exception import measure as measure_two_lane
        return measure_two_lane(source_dir)
    return measure_single_lane(source_dir)


def finalize(attempt,output):
    attempt=Path(attempt).resolve();output=Path(output)
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Use a fresh saved attempt')
    config=json.loads(require(attempt,'config.json').read_text())
    if (config.get('law_id'),config.get('cell_id'),config.get('actor'))!=(
            'NRS-484B-127-2','C102372','heavy_vehicle_driver'):
        raise ValueError('Frozen truck-follow assignment differs')
    suffix=config.get('case_suffix')
    if suffix not in ('probe_1','probe_2','two_lane_exception','passing_overtake',
                      'passing_hold','conditions_steady','conditions_lead_brake'):
        raise ValueError('Unknown exact truck-follow case')
    if config.get('case_id')!='training__C102372__NRS-484B-127-2__heavy_vehicle_driver__'+str(suffix):
        raise ValueError('Exact truck-follow case identity differs')
    manifest=json.loads(require(attempt,'capture/manifest.json').read_text())
    if manifest.get('frames')!=FRAMES or manifest.get('extraction_confirmed') is not True:
        raise ValueError('Complete original 480-frame extraction absent')
    require(attempt,'native_samples.jsonl')
    value=measure(attempt,suffix)
    groups={name:rows(require(attempt,name)) for name in ROWS}
    if any(len(group)!=FRAMES for group in groups.values()):
        raise ValueError('Original truck capture row count differs')
    first=groups['video_frames.jsonl'][0].get('time_s')
    if type(first) not in (int,float):raise ValueError('First source timestamp absent')
    prior=None
    for index,(native,trace,evidence,join) in enumerate(zip(*(groups[name] for name in ROWS))):
        frame=join.get('carla_frame');expected_time=first+index/20
        if type(frame) is not int or (prior is not None and frame<=prior):
            raise ValueError('Original CARLA frame order differs')
        prior=frame
        if (join.get('video_frame'),join.get('native_frame'),native.get('native_frame'),
                native.get('carla_frame'),trace.get('frame'),evidence.get('original_frame'))!=(
                index,index,index,frame,frame,frame):
            raise ValueError('Original truck frame join differs')
        if any(type(t) not in (int,float) or not math.isclose(t,expected_time,abs_tol=1e-3)
               for t in (join.get('time_s'),native.get('time_s'))):
            raise ValueError('Original truck timestamp join differs')
        if any(type(t) not in (int,float) or not math.isclose(t,native.get('elapsed_s',-1),abs_tol=.002)
               for t in (trace.get('time_s'),evidence.get('recording_time_s'))):
            raise ValueError('Native trace/evidence timestamp differs')
        ego=native.get('ego',{});lead=native.get('lead',{})
        if len(ego.get('body_vertices_m',[]))<8 or len(lead.get('body_vertices_m',[]))<8:
            raise ValueError('Full original truck body vertices absent')
        if evidence.get('ego',{}).get('body_vertices_m')!=ego['body_vertices_m']:
            raise ValueError('Original ego truck body differs from capture')
        if len(trace.get('position_m',[]))<2 or any(abs(a-b)>1e-3 for a,b in zip(
                trace['position_m'][:2],ego.get('center_xy_m',[]))):
            raise ValueError('Original ego truck pose differs from trace')
    videos={name:frames(require(attempt,name)) for name in VIDEOS}
    if any(count!=FRAMES for count in videos.values()):
        raise ValueError('Original four-view video frame count differs')
    recording=[]
    for channel in config['recording_description']['channels']:
        name=channel['name'];relative='channels/'+name+'.jsonl'
        if len(rows(require(attempt,relative)))!=FRAMES:
            raise ValueError('Original truck channel row count differs: '+name)
        recording.append({'name':name,'unit':channel['unit'],'reference':relative})
    recording.append({'name':'conditions_permit','unit':'structured',
                      'reference':'following_context.json'})
    passing_family=suffix in ('passing_overtake','passing_hold')
    conditions=suffix in ('conditions_steady','conditions_lead_brake')
    expected=(suffix=='conditions_lead_brake') if conditions else (
        (suffix=='passing_overtake') if passing_family else
        ('above' if suffix=='probe_1' else 'below'))
    observed=(value['lead_braking_gap_compression_observed'] if conditions else
              value['passing_sequence_observed'] if passing_family else
              value['relation_to_500ft'])
    matched=observed==expected
    measurement_key=('truck_conditions_event' if conditions else
                     'truck_passing_sequence' if passing_family else 'truck_following_gap')
    result={'case_id':config['case_id'],'measured_values':{measurement_key:value},
        'target_checks':[{'target':'lead_braking_gap_compression_observed' if conditions else
                          'passing_sequence_observed' if passing_family else 'relation_to_500ft',
            'requested':expected,'measured':observed,
            'method':'source-hashed original truck body/road-arc/obstacle sequence' if conditions else
                     'source-hashed original truck body/lane sequence' if passing_family else
                     'source-hashed original body road-arc gap',
            'tolerance':0,'matched':matched,'physical_cause_confirmed':False,
            'cause_evidence':['native_samples.jsonl','road.xodr','following_context.json']}],
        'setup_confirmed':True,'behavior_attempted':True,'maneuver_completed':True,
        'termination_reason':'full saved 24 s diagnostic','trace_reference':'trace.jsonl',
        'video_references':list(VIDEOS),'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':config['recording_description'],'recording_evidence':recording,
        'physical_failure_flags':['conditions_permit_and_obstacle_pixels_require_independent_review'] if conditions else
                                 ['passing_clearance_and_pixels_require_independent_review'] if passing_family else
                                 ['conditions_permit_and_pixels_require_independent_review'],
        'realized_observables':{'minimum_truck_surface_gap' if conditions else
                                'minimum_truck_body_clearance' if passing_family else
                                'minimum_truck_surface_gap':{
            'value':value['minimum_surface_gap_m'] if conditions else
                    value['minimum_body_clearance_m'] if passing_family else value['min_surface_gap_m'],
            'unit':'m','method':'source-hashed truck road-arc surface gap' if conditions else
                              'source-hashed truck body clearance' if passing_family else
                              'source-hashed road-arc body gap','time_window':'saved 24 s',
            'statistic':'minimum','reference':'native_samples.jsonl'}},
        'provenance_kind':'native' if json.loads((attempt/'following_context.json').read_text())[
            'source_kind']=='native_observation' else 'synthetic_cpu',
        'accepted':False,'legal_verdict_claimed':False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report={'format':'c102372-saved-analysis-v1','case_id':config['case_id'],
        'candidate_id':config['candidate_id'],
        'measurements':{measurement_key:{'method':'measure','value':value,
            'sources':{name:sha(require(attempt,name)) for name in
                ('native_samples.jsonl','following_context.json','road.xodr')}}},
        'original_joins':{name:sha(require(attempt,name)) for name in ROWS},
        'video_frames':videos,'scope':'saved CPU diagnostic; no legal verdict or acceptance'}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    with (attempt/'result.json').open('x') as stream:
        json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output),sort_keys=True))
