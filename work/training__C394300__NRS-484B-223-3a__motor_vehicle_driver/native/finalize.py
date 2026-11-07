"""Case-specific saved measurements for pinned compatibility; no legal verdict."""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from measure_saved import measure

SOURCES=('scene.xodr','road_geometry.json','declared_purpose.json','native_samples.jsonl')


def _required(folder,name):
    path=Path(folder)/name
    if not path.is_file():raise ValueError('Missing required source: '+name)
    return path


def _sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def purpose_movement(folder):
    result=measure(folder)
    return {'source_kind':result['source_kind'],
            'declared_purpose':result['declared_purpose'],
            'declared_purpose_is_observed_driver_intent':False,
            'movement':result['measured'],
            'requested_movement_observed_in_saved_rows':result['requested_movement_observed_in_saved_rows'],
            'legal_verdict':None}


def analysis_report(folder):
    folder=Path(folder)
    config=json.loads(_required(folder,'config.json').read_text())
    for name in SOURCES:_required(folder,name)
    return {'format':'c394300-3a-saved-analysis-v1','case_id':config['case_id'],
            'draft_only':True,'selected':False,
            'measurements':{'center_turn_purpose_and_movement':{
                'method':'purpose_movement','value':purpose_movement(folder),
                'sources':{name:_sha(folder/name) for name in SOURCES}}},
            'physical_acceptance_claimed':False}


def _rows(folder,name):
    return [json.loads(line) for line in _required(folder,name).read_text().splitlines() if line.strip()]


def original_joins(folder,count):
    names=('trace.jsonl','capture/evidence.jsonl','video_frames.jsonl',
           'native_samples.jsonl','body_history.jsonl','capture/native/frames.jsonl')
    sources=[_rows(folder,name) for name in names]
    if any(len(rows)!=count for rows in sources):
        raise ValueError('Original trace/evidence/body/frame counts differ')
    previous_frame=-1;previous_time=-math.inf
    for index,(trace,evidence,mapping,sample,body,capture) in enumerate(zip(*sources)):
        frame=mapping.get('native_frame');time=float(mapping['time_s'])
        if type(frame) is not int or frame<=previous_frame or time<=previous_time or \
                mapping.get('video_frame')!=index or mapping.get('carla_frame')!=frame:
            raise ValueError('Original frame/time mapping invalid')
        previous_frame=frame;previous_time=time
        if any(row.get(key)!=frame for row,key in ((trace,'frame'),(evidence,'original_frame'),
                (sample,'native_frame'),(body,'frame'),(capture,'frame'))):
            raise ValueError('Original Native frame join differs')
        if any(abs(float(row[key])-time)>1e-4 for row,key in ((trace,'time_s'),
                (evidence,'recording_time_s'),(sample,'time_s'),(body,'time_s'),
                (capture,'time_s'))):
            raise ValueError('Original Native timestamp join differs')
        if abs(float(capture['simulation_time'])-
               float(evidence['replay_simulation_time_s']))>1e-4:
            raise ValueError('Original replay simulation timestamp join differs')
        captured={(round(v[0],5),round(v[1],5)) for v in evidence['ego']['body_vertices_m']}
        measured={(round(v[0],5),round(v[1],5)) for v in sample['native_body_xy_m']}
        historical={(round(v[0],5),round(v[1],5)) for v in body['body_vertices_m']}
        if captured!=measured or measured!=historical or len(measured)!=4:
            raise ValueError('Original full body differs from saved measurement')
    manifest=json.loads(_required(folder,'capture/manifest.json').read_text())
    if manifest.get('extraction_confirmed') is not True or manifest.get('frames')!=count:
        raise ValueError('Original capture extraction incomplete')
    return {'frames':count,'first_frame':sources[2][0]['native_frame'],
            'last_frame':sources[2][-1]['native_frame'],
            'source_hashes':{name:_sha(Path(folder)/name) for name in names}}


def _video_frames(path):
    result=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=nb_read_frames','-of','default=noprint_wrappers=1:nokey=1',
        str(path)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if result.returncode or not result.stdout.strip().isdigit():
        raise ValueError('Source video decode failed: '+path.name)
    return int(result.stdout.strip())


def capture_provenance(attempt,count):
    from worker_exchange.common import digest, within
    from worker_exchange.native_output import provenance_record
    record=provenance_record(attempt)
    seal_path=attempt/'capture-seal.json'
    if not seal_path.is_file():
        return {'source_kind':record['provenance_kind'],
                'diagnostic_fixture':record['diagnostic_fixture'],
                'native_executed':False},False
    seal=json.loads(seal_path.read_text());sources=seal.get('sources')
    required={'trace.jsonl','video_frames.jsonl','capture/evidence.jsonl',
        'native_samples.jsonl','body_history.jsonl','capture/native/frames.jsonl',
        'scene.xodr','road_geometry.json','declared_purpose.json',
        'overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'}
    if not isinstance(sources,dict) or not required<=set(sources) or digest(sources)!=seal.get('source_digest'):
        raise ValueError('Native capture seal source inventory incomplete')
    for name,expected in sources.items():
        if _sha(within(attempt,name))!=expected:
            raise ValueError('Sealed original changed: '+name)
    marker_path=attempt/'acquisition-provenance.json'
    marker=json.loads(marker_path.read_text()) if marker_path.is_file() else {}
    codes=seal.get('encoder_exit_codes')
    cameras={'overview','approach','reference_corner','driver_reference'}
    native=(record['provenance_kind']=='native' and
        record['diagnostic_fixture'] is False and
        seal.get('format')=='worker-sealed-capture-v2' and
        seal.get('provenance_kind')=='native' and
        seal.get('diagnostic_fixture') is False and
        seal.get('frames')==count and
        seal.get('events')==['capture_finished','encoders_closed','restoration_verified'] and
        seal.get('restoration',{}).get('restored') is True and
        isinstance(codes,dict) and set(codes)==cameras and
        all(type(code) is int and code==0 for code in codes.values()) and
        marker.get('diagnostic_fixture') is not True and
        marker.get('native_executed') is not False)
    return {'source_kind':record['provenance_kind'],
            'diagnostic_fixture':record['diagnostic_fixture'],
            'native_executed':native},native


def finalize(attempt,output):
    from worker_exchange.native_output import validate_result, provenance_record
    attempt=Path(attempt).resolve();output=Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain original finalization; use a fresh attempt')
    config=json.loads(_required(attempt,'config.json').read_text())
    count=config['duration_s']*config['rate_hz']
    report=analysis_report(attempt)
    joins=original_joins(attempt,count)
    videos=[name+'.mkv' for name in ('overview','approach','reference_corner','driver_reference')]
    counts={name:_video_frames(_required(attempt,name)) for name in videos}
    if set(counts.values())!={count}:raise ValueError('Source camera frame count differs')
    provenance,native=capture_provenance(attempt,count)
    movement=dict(report['measurements']['center_turn_purpose_and_movement']['value'])
    movement.pop('legal_verdict',None)
    observed=movement['requested_movement_observed_in_saved_rows']
    evidence=[]
    for channel in config['recording_description']['channels']:
        reference='channels/'+channel['name']+'.jsonl'
        _required(attempt,reference)
        evidence.append({'name':channel['name'],'unit':channel['unit'],'reference':reference})
    result={'case_id':config['case_id'],'measured_values':movement,
        'target_checks':[{'target':'source-declared center-turn purpose and saved full-body movement',
            'requested':config['case_suffix'],'measured':observed,
            'method':'source-declared purpose plus original Native lane, road and full-body frame rows',
            'tolerance':'50 ms source frame bracket; declaration is not observed driver intent',
            'matched':bool(observed),'physical_cause_confirmed':False,
            'cause_evidence':['declared_purpose.json','road_geometry.json','native_samples.jsonl']}],
        'setup_confirmed':native,'behavior_attempted':native,'maneuver_completed':native and bool(observed),
        'termination_reason':'full original duration retained',
        'physical_failure_flags':['physical_center_lane_and_driver_purpose_unverified'],
        'trace_reference':'trace.jsonl','video_references':videos,
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':config['recording_description'],'recording_evidence':evidence,
        'realized_observables':{'center_full_body_frames':{
            'value':movement['movement']['center_full_body_frames'],'unit':'frames',
            'method':'saved source-bound full-body center-lane occupancy',
            'time_window':'entire original 24 s attempt','statistic':'count',
            'reference':'native_samples.jsonl'}},
        'provenance_kind':'native' if native else 'synthetic_local_diagnostic','accepted':False,
        'legal_verdict_claimed':False}
    validate_result(result)
    report.update(original_joins=joins,video_frames=counts,
        acquisition_provenance=provenance,
        scope='saved original sources and video decode; physical purpose and legal verdict unverified')
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (attempt/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output)))


if __name__=='__main__':main()
