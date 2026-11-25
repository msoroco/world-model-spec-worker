"""Saved-only C382355 right-only-lane purpose observation; no legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from measure_purpose import measure_lane_use as measure


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    path=Path(path)
    if not path.is_file():raise ValueError("Missing required source: "+path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def verify_original_joins(attempt,expected_frames):
    attempt=Path(attempt)
    trace=rows(attempt/'trace.jsonl')
    evidence=rows(attempt/'capture/evidence.jsonl')
    mapping=rows(attempt/'video_frames.jsonl')
    motion=rows(attempt/'native_samples.jsonl')
    body=rows(attempt/'body_history.jsonl')
    if not all(len(source)==expected_frames for source in (trace,evidence,mapping,motion,body)):
        raise ValueError("Original trace/evidence/body/frame counts differ")
    previous_frame=-1;previous_time=-math.inf
    for index,(t,e,m,n,b) in enumerate(zip(trace,evidence,mapping,motion,body)):
        frame=m.get('native_frame');time=float(m['time_s'])
        if frame<=previous_frame or time<=previous_time or m['video_frame']!=index:
            raise ValueError("Original frame/time mapping is not monotonic")
        previous_frame=frame;previous_time=time
        if any(item!=frame for item in (t.get('frame'),e.get('original_frame'),n.get('native_frame'),b.get('frame'))):
            raise ValueError("Original Native frame join differs")
        if any(abs(float(item)-time)>1e-4 for item in
               (t['time_s'],e['recording_time_s'],n['time_s'],b['time_s'])):
            raise ValueError("Original Native timestamp join differs")
        captured={(round(v[0],5),round(v[1],5)) for v in e['ego']['body_vertices_m']}
        measured={(round(v[0],5),round(v[1],5)) for v in n['native_body_xy_m']}
        body_history={(round(v[0],5),round(v[1],5)) for v in b['body_vertices_m']}
        if captured!=measured or measured!=body_history or len(measured)!=4:
            raise ValueError("Original full body differs from saved measurement")
    meta=json.loads((attempt/'capture/manifest.json').read_text())
    if not meta.get('extraction_confirmed') or meta.get('frames')!=expected_frames:
        raise ValueError("Original capture extraction incomplete")
    return {'frames':expected_frames,'first_frame':mapping[0]['native_frame'],
            'last_frame':mapping[-1]['native_frame'],
            'first_time_s':mapping[0]['time_s'],'last_time_s':mapping[-1]['time_s'],
            'source_hashes':{name:sha(attempt/name) for name in
              ('trace.jsonl','capture/evidence.jsonl','video_frames.jsonl',
               'native_samples.jsonl','body_history.jsonl','capture/manifest.json')}}


def video_frames(path):
    if not path.is_file():raise ValueError("Missing required source: "+path.name)
    completed=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=nb_read_frames','-of','default=noprint_wrappers=1:nokey=1',str(path)],
        text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if completed.returncode or not completed.stdout.strip().isdigit():
        raise ValueError("Source video decode failed: "+path.name+" "+completed.stderr[-300:])
    return int(completed.stdout.strip())


def capture_provenance(attempt, count):
    from worker_exchange.common import digest, within
    from worker_exchange.native_output import provenance_record
    record = provenance_record(attempt)
    seal_path = attempt/'capture-seal.json'
    if not seal_path.is_file():
        return {'source_kind':record['provenance_kind'],
                'diagnostic_fixture':record['diagnostic_fixture'],
                'native_executed':False}, False
    seal = json.loads(seal_path.read_text())
    sources = seal.get('sources')
    required = {'trace.jsonl','video_frames.jsonl','capture/evidence.jsonl',
                'native_samples.jsonl','body_history.jsonl','road_geometry.json',
                'overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'}
    if not isinstance(sources,dict) or not required <= set(sources) or digest(sources)!=seal.get('source_digest'):
        raise ValueError('Native capture seal source inventory incomplete')
    for name, expected in sources.items():
        if sha(within(attempt,name))!=expected:
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
            'native_executed':native}, native


def measure_lane_purpose(attempt):
    attempt=Path(attempt)
    result=measure(attempt/'native_samples.jsonl',attempt/'road_geometry.json')
    value={key:result[key] for key in ('approach_window_s','intersection_window_s',
        'exit_window_s','full_body_in_right_only_lane_approach_samples',
        'right_only_lane_identity_fraction','observed_subsequent_movement',
        'right_only_lane_design_native_verified')}
    return {'value':value,'method':'measure_lane_purpose',
            'sources':{name:sha(attempt/name) for name in ('native_samples.jsonl','road_geometry.json')}}


def derive_channels(attempt, config):
    """Rebuild analysis channels from retained original source rows.

    Saved processing copies acquisition and rebuilds derived channels. A Native
    capture may already contain channels, but these copies are never treated as
    independent evidence for the selected analysis.
    """
    channel_dir = attempt/'channels'
    channel_dir.mkdir(exist_ok=True)
    samples = rows(attempt/'native_samples.jsonl')
    mapping = rows(attempt/'video_frames.jsonl')
    geometry = json.loads((attempt/'road_geometry.json').read_text())
    if len(samples) != len(mapping):
        raise ValueError('Original channel source counts differ')
    names = [item['name'] for item in config['recording_description']['channels']]
    for name in names:
        path = channel_dir/(name+'.jsonl')
        values = []
        for sample, mapped in zip(samples, mapping):
            if name == 'drv.turning':
                value = {'authored_intent': 'right turn from adjacent approach lane',
                         'observed_forward':sample['native_forward_xy']}
            elif name in ('st.intersection','st.turn_lane'):
                value = geometry
            elif name == 'kin.heading':
                value = math.degrees(math.atan2(sample['native_forward_xy'][1],sample['native_forward_xy'][0]))
            elif name == 'rel.occupies':
                value = sample['native_body_xy_m']
            elif name == 'native_body_pose_control':
                value = sample
            elif name == 'camera_frame_join':
                value = mapped
            else:
                raise ValueError('Unknown derived channel: '+name)
            values.append({'time_s':sample['time_s'],'value':value})
        path.write_text(''.join(json.dumps(value)+'\n' for value in values))


def finalize(attempt,output):
    attempt=Path(attempt).resolve();output=Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain original finalization; use a fresh attempt')
    config=json.loads((attempt/'config.json').read_text())
    derive_channels(attempt,config)
    requested_count=config['duration_s']*config['rate_hz'];count=round(requested_count)
    if abs(requested_count-count)>1e-6 or count<2:
        raise ValueError('Recording duration/rate does not yield an integral frame count')
    original=verify_original_joins(attempt,count)
    provenance,native=capture_provenance(attempt,count)
    measured=measure_lane_purpose(attempt)
    videos=[f'{name}.mkv' for name in ('overview','approach','reference_corner','driver_reference')]
    video_counts={name:video_frames(attempt/name) for name in videos}
    if any(frames!=count for frames in video_counts.values()):
        raise ValueError('Source camera frame count differs from delivered trace')
    actual=measured['value']
    requested='right_turn_follows'
    observed=actual['observed_subsequent_movement']
    lane_condition=(actual['full_body_in_right_only_lane_approach_samples'] and
                    actual['right_only_lane_identity_fraction']==1) if config['case_suffix']=='controlled_1' else (
                    not actual['full_body_in_right_only_lane_approach_samples'] and
                    actual['right_only_lane_identity_fraction']==0)
    matched=observed==requested and lane_condition
    description=config['recording_description'];recording_evidence=[]
    for channel in description['channels']:
        name=channel['name'];reference='channels/'+name+'.jsonl'
        if not (attempt/reference).is_file():raise ValueError('Missing required source: '+reference)
        recording_evidence.append({'name':name,'unit':channel['unit'],'reference':reference})
    for context in description['context_inputs']:
        if not (attempt/'context.json').is_file():raise ValueError('Missing required source: context.json')
        recording_evidence.append({'name':context['name'],'unit':context['unit'],
                                   'reference':'context.json'})
    result={'case_id':config['case_id'],'measured_values':actual,
      'target_checks':[{'target':'adjacent-lane approach then right turn; right-only-lane approach condition absent',
        'requested':requested,'measured':observed,
        'method':'original Native body, road/lane IDs and ordered completed exit',
        'tolerance':'exact right-turn exit and no sampled approach center in the right-only lane','matched':matched,
        'physical_cause_confirmed':False,
        'cause_evidence':['road_geometry.json','native_samples.jsonl']}],
      'setup_confirmed':native and actual['right_only_lane_design_native_verified'],
      'behavior_attempted':native,'maneuver_completed':native and observed in ('right_turn_follows','straight_follows'),
      'termination_reason':'full original duration retained',
      'physical_failure_flags':['right_only_lane_design_and_pixels_unverified']+
           ([] if matched else ['ordered_lane_use_target_not_measured']),
      'trace_reference':'trace.jsonl','video_references':videos,
      'video_frame_map_reference':'video_frames.jsonl',
      'recording_description':description,'recording_evidence':recording_evidence,
      'realized_observables':{'sampled_approach_right_only_lane_identity_fraction':
          {'value':actual['right_only_lane_identity_fraction'],'unit':'fraction',
           'method':'fraction of original sampled approach road/lane IDs matching surveyed right-only lane',
           'time_window':'before first body intersection entry',
           'statistic':'fraction','reference':'native_samples.jsonl',
           'sample_window_s':actual['approach_window_s']}},
      'provenance_kind':'native' if native else 'synthetic_local_diagnostic',
      'accepted':False,'legal_verdict_claimed':False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report={'format':'c382355-right-only-lane-saved-analysis-v1','case_id':config['case_id'],
      'candidate_id':config['candidate_id'],
      'measurements':{'right_only_lane_subsequent_movement':measured},
      'original_joins':original,'video_frames':video_counts,
      'acquisition_provenance':provenance,
      'scope':'saved original Native sources and source-video decode; right-only lane design, purpose and legal verdict unverified'}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    with (attempt/'result.json').open('x') as stream:
        json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output)))


if __name__=='__main__':main()
