"""Analyze saved sidewalk sources, preserving uncertainty and original bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import math
import struct

from measure_sidewalk import measure
from audio_source import load_pcm

SOURCES=('sidewalk-actors.jsonl','video_frames.jsonl','camera-frames.jsonl',
         'pedestrian-microphone.json','pedestrian-microphone-frames.jsonl',
         'sidewalk-map-readback.json','road.xodr')


def required(root,name):
    path=Path(root)/name
    if not path.is_file():raise ValueError('Missing required source: '+name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_electric_sources(attempt, config):
    """Fail closed on missing original device and source-backed type/power identity."""
    if config.get('device_class') not in ('electric_bicycle', 'electric_scooter'):
        raise ValueError('Exact electric device class required')
    evidence = json.loads(required(attempt, 'electric-device-evidence.json').read_text())
    if (evidence.get('source_kind') != 'original_native_electric_device_binding' or
            evidence.get('device_class_requested') != config['device_class'] or
            evidence.get('blueprint_id') != config.get('source_bound_blueprint_id')):
        raise ValueError('Original electric class/type binding differs')
    rows = [json.loads(line) for line in required(attempt, 'sidewalk-actors.jsonl').read_text().splitlines()]
    if not rows or any(row.get('rider_device_blueprint') != evidence['blueprint_id'] or
                       row.get('rider_id') != evidence.get('actor_id') for row in rows):
        raise ValueError('Original electric actor/type readback differs')
    for prefix in ('native_asset', 'legal_class', 'device_type', 'motor_power'):
        path = Path(config.get(prefix + '_source', ''))
        digest = config.get(prefix + '_sha256')
        if not path.is_file() or sha(path) != digest or evidence.get('source_hashes', {}).get(prefix) != digest:
            raise ValueError('Electric ' + prefix + ' source/hash binding missing or stale')
    return {'device_class_requested': config['device_class'],
            'blueprint_id': evidence['blueprint_id'],
            'source_hashes': evidence['source_hashes'],
            'independent_class_review_complete': False,
            'original_motor_power_measured': False}


def device_and_sidewalk(observed,context):
    return {'rider_id':observed['rider_id'],
            'pedestrian_id':observed['pedestrian_id'],
            'device_class_independently_verified':False,
            'sidewalk_designation_independently_verified':False}


def yield_observation(observed,context):
    return {'first_rider_pause_frame':observed['first_rider_pause_frame'],
            'first_footprint_overlap_frame':observed['first_footprint_overlap_frame'],
            'right_of_way_legal_verdict':None}


def source_audio_order(observed,context):
    return {'first_microphone_pulse_video_frame_approx':observed['first_microphone_pulse_video_frame_approx'],
            'first_footprint_overlap_frame':observed['first_footprint_overlap_frame'],
            'engineering_margin_observed':observed['pulse_precedes_overlap_with_engineering_margin'],
            'audible_signal_identity_verified':False}


def observation_streams(attempt,config):
    attempt=Path(attempt)
    actors=[json.loads(line) for line in required(attempt,'sidewalk-actors.jsonl').read_text().splitlines()]
    images=[json.loads(line) for line in required(attempt,'camera-frames.jsonl').read_text().splitlines()]
    context=json.loads(required(attempt,'sidewalk-map-readback.json').read_text())
    metadata=json.loads(required(attempt,'pedestrian-microphone.json').read_text())
    raw=load_pcm(attempt,metadata)
    samples=struct.unpack('<'+'h'*(len(raw)//2),raw)
    directory='saved-observations' if (attempt/'recorded-observations').exists() else 'recorded-observations'
    output=attempt/directory;output.mkdir(exist_ok=False)
    names={channel['name'] for channel in config['recording_description']['channels']}
    expected={'rider_and_pedestrian_footprints','pedestrian_location_audio',
              'sidewalk_map_context','four_source_views'}
    if names!=expected:raise ValueError('Selected observation channels changed')
    streams={name:[] for name in names}
    for i,actor in enumerate(actors):
        t=actor['time_s']
        span=samples[i*400:(i+1)*400]
        if not span:raise ValueError('Pedestrian microphone source too short')
        rms=math.sqrt(sum(v*v for v in span)/len(span))/32768
        values={'rider_and_pedestrian_footprints':{
                    'rider_xyz_m':actor['rider_xyz_m'],
                    'pedestrian_xyz_m':actor['pedestrian_xyz_m'],
                    'rider_bbox_extent_xyz_m':actor['rider_bbox_extent_xyz_m'],
                    'pedestrian_bbox_extent_xyz_m':actor['pedestrian_bbox_extent_xyz_m'],
                    'rider_velocity_xyz_mps':actor['rider_velocity_xyz_mps']},
                'pedestrian_location_audio':{'window_rms_relative':rms,
                    'sample_rate_hz':metadata['sample_rate_hz'],
                    'clock_calibrated_for_legal_order':False},
                'sidewalk_map_context':{'road_id':context['road_id'],
                    'lane_id':context['lane_id'],
                    'municipal_applicability_verified':False},
                'four_source_views':{row['camera']:row.get('rgb_sha256','synthetic_fixture')
                    for row in images[4*i:4*i+4]}}
        for name,value in values.items():
            streams[name].append({'time_s':t,'value':value})
    paths={}
    for name,rows in streams.items():
        relative=directory+'/'+name+'.jsonl'
        (attempt/relative).write_text(''.join(json.dumps(row,separators=(',',':'))+'\n'
                                              for row in rows))
        paths[name]=relative
    return paths


def finalize(attempt,output):
    from worker_exchange.native_output import provenance_record,write_result

    attempt,output=Path(attempt).resolve(),Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Use fresh recorded-only analysis output')
    config=json.loads(required(attempt,'config.json').read_text())
    if (config['cell_id'],config['law_id'],config['actor'])!= (
            'C230266','LVMC-11-40-180-C','cycle_or_scooter_operator'):
        raise ValueError('Frozen sidewalk assignment identity changed')
    electric = validate_electric_sources(attempt, config) if config.get('device_class') in (
        'electric_bicycle', 'electric_scooter') else None
    for name in SOURCES:required(attempt,name)
    observed=measure(attempt)
    stream_paths=observation_streams(attempt,config)
    source_hashes={name:sha(required(attempt,name)) for name in SOURCES}
    if electric is not None:
        source_hashes['electric-device-evidence.json'] = sha(required(attempt, 'electric-device-evidence.json'))
    microphone=json.loads(required(attempt,'pedestrian-microphone.json').read_text())
    source_hashes[microphone['pcm_path']]=sha(required(attempt,microphone['pcm_path']))
    contract=json.loads(required(attempt,'measurement-contract.json').read_text())
    methods={'covered_device_sidewalk':'device_and_sidewalk',
             'pedestrian_priority_response':'yield_observation',
             'audible_signal_order':'source_audio_order'}
    functions={'covered_device_sidewalk':device_and_sidewalk,
               'pedestrian_priority_response':yield_observation,
               'audible_signal_order':source_audio_order}
    measurements={}
    for requirement in contract['requirements']:
        key=requirement['output_key']
        if methods.get(key)!=requirement['method']:
            raise ValueError('Selected sidewalk measurement method changed')
        measurements[key]={'method':methods[key],'value':functions[key](observed,config),
                           'sources':{name:source_hashes[name]
                                      for name in requirement['inputs']}}
    provenance=provenance_record(attempt)
    original=provenance['provenance_kind']=='native' and not provenance['diagnostic_fixture']
    target=config.get('target_request',{})
    observed_pause=observed['first_rider_pause_frame'] is not None
    observed_signal=observed['first_microphone_pulse_video_frame_approx'] is not None
    matched=(observed_pause==target.get('pause_requested') and
             observed_signal==target.get('signal_requested'))
    result={'case_id':config['case_id'],'measured_values':observed,
            'target_checks':[{'target':'requested sidewalk rider pause and microphone signal',
                'requested':target,
                'measured':{'pause_observed':observed_pause,'audio_pulse_observed':observed_signal,
                            'full_pass_frame':observed['first_full_ahead_frame']},
                'method':'original actor, camera and microphone source join',
                'tolerance':'engineering observation only; legal judgment deferred',
                'matched':matched,'physical_cause_confirmed':False,
                'cause_evidence':list(source_hashes)}],
            'setup_confirmed':False,'behavior_attempted':original,
            'maneuver_completed':original and observed['first_full_ahead_frame'] is not None,
            'termination_reason':'600 source frames retained; sound identity and legal review pending',
            'physical_failure_flags':[] if matched else ['requested_sidewalk_behavior_not_observed'],
            'trace_reference':'trace.jsonl',
            'video_references':[name+'.mkv' for name in (
                'overview','approach','reference_corner','driver_reference')],
            'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':config['recording_description'],
            'recording_evidence':[{'name':channel['name'],'unit':channel['unit'],
                                   'reference':stream_paths[channel['name']]}
                                  for channel in config['recording_description']['channels']],
            'realized_observables':{'minimum_lateral_footprint_gap_m':{
                'value':observed['minimum_lateral_footprint_gap_m'],'unit':'m',
                'method':'joined original rider and pedestrian bounding boxes',
                'time_window':'600 original frames','statistic':'minimum',
                'reference':'sidewalk-actors.jsonl'}},
            'provenance_kind':provenance['provenance_kind'],
            'diagnostic_fixture':provenance['diagnostic_fixture'],
            'physical_acceptance_claimed':False,'legal_verdict_claimed':False}
    if electric is not None:
        result['electric_device_evidence'] = electric
    write_result(attempt,result)
    report={'format':'c230266-sidewalk-source-analysis-v1',
            'case_id':config['case_id'],'analysis_complete':True,
            'measurements':measurements,'source_hashes':source_hashes,
            'provenance':provenance,'legal_verdict_claimed':False,
            'physical_acceptance_claimed':False}
    if electric is not None:
        report['electric_device_evidence'] = electric
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output)))
