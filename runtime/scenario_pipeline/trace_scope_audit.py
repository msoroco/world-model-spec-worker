"""Read-only streaming verification of full delivered traces against source frames."""
import hashlib
import json
import math
import re
from pathlib import Path
from batch_pipeline.store import atomic


def scenes(path):
    decoder=json.JSONDecoder()
    with Path(path).open() as stream:
        buffer='';started=False
        while True:
            chunk=stream.read(1024*1024)
            buffer+=chunk
            if not started:
                at=buffer.find('[')
                if at<0:
                    if not chunk:raise ValueError('Missing scenes array')
                    continue
                if re.sub(r'\s+','',buffer[:at])!='{"scenes":':raise ValueError('Unexpected trace envelope')
                buffer=buffer[at+1:];started=True
            while True:
                buffer=buffer.lstrip()
                if buffer.startswith(','):buffer=buffer[1:].lstrip()
                if buffer.startswith(']'):
                    remainder=buffer[1:]+stream.read()
                    if remainder.strip()!='}':raise ValueError('Unexpected trailing trace content')
                    return
                try:scene,end=decoder.raw_decode(buffer)
                except json.JSONDecodeError:
                    if not chunk:raise ValueError('Truncated trace scene')
                    break
                yield scene
                buffer=buffer[end:]


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def verify(attempt,trace):
    path=attempt/'traffic_spec/trace.json';report=attempt/'traffic_spec/adapter_report.json'
    receipt_path=attempt/'trace_scope_audit.json';digest=sha(path)
    source_sha=sha(attempt/'trace.jsonl');map_sha=sha(attempt/'video_frames.jsonl')
    identity={'trace_sha256':digest,'source_sha256':source_sha,'frame_map_sha256':map_sha,'adapter_report_sha256':sha(report),'audit_revision':2}
    if receipt_path.exists():
        previous=json.loads(receipt_path.read_text())
        if previous.get('passed') and 'authored_speed_control_applicability' in previous and 'subject_speeds_mps' in previous and all(previous.get(k)==v for k,v in identity.items()):
            if 'legal_verdict' in previous:
                previous.pop('legal_verdict');atomic(receipt_path,previous)
            return previous
    mapping=[json.loads(line) for line in (attempt/'video_frames.jsonl').read_text().splitlines()]
    if len(mapping)!=len(trace):raise ValueError('Trace/source camera count mismatch')
    adapter=json.loads(report.read_text())
    if not adapter.get('decoder_validation',{}).get('passed'):raise ValueError('Missing successful Lean decoder receipt')
    portions=adapter.get('authored_speed_control_portions',[])
    control_applicability=[dict(governed_region=p['governed_region'],speed_mps=p['speed_mps'],applicable_frames=[]) for p in portions]
    count=0;subject_speeds=[];all_motor=True;highway=True;posted_seen=False
    for i,scene in enumerate(scenes(path)):
        if i>=len(trace):raise ValueError('Delivered trace contains extra scenes')
        point=trace[i];frame=mapping[i]
        if frame['carla_frame']!=point['frame'] or abs(frame['time_s']-point['time_s'])>1e-6:raise ValueError('Camera/source frame mapping mismatch')
        if scene['t']!=round(point['time_s']*1000):raise ValueError('Delivered trace/source timestamp mismatch')
        users=[u for u in scene['users'] if u['track']==scene['subject']]
        if len(users)!=1:raise ValueError('Trace lacks unique subject')
        speed=users[0].get('kin',{}).get('speed')
        if speed is None or not math.isfinite(speed) or abs(speed-point['speed_mps'])>1e-6:raise ValueError('Delivered/source speed mismatch')
        subject_speeds.append(speed)
        all_motor=all_motor and 'motor_vehicle' in users[0].get('classes',[])
        highway=highway and any(s['kind']=='lane' for s in scene['structures'])
        posted_seen=posted_seen or any(d['kind']=='speed_limit_sign' and d.get('governs') for d in scene['devices'])
        if control_applicability and scene['subject'] not in scene.get('occupancy_observed',[]):raise ValueError('Delivered Core does not establish authored-portion occupancy for subject')
        for portion in control_applicability:
            region=portion['governed_region']
            signs=[d for d in scene['devices'] if d['kind']=='speed_limit_sign' and region in d.get('governs',[]) and abs(d.get('speed_value',-1)-portion['speed_mps'])<1e-6]
            if len(signs)!=1:raise ValueError('Delivered authored portion lacks its unique observed native speed sign')
            portion['applicable_frames'].append([scene['subject'],region] in scene['occupies'])
        count+=1
    if count!=len(trace) or count!=adapter['frames']:raise ValueError('Full delivered trace count mismatch')
    if sha(path)!=digest:raise ValueError('Delivered trace changed during review')
    receipt=dict(identity,passed=True,frames=count,time_range_s=[trace[0]['time_s'],trace[-1]['time_s']],
                 full_trace_unchanged=True,subject_speeds_mps=subject_speeds,all_subject_motor_vehicle=all_motor,all_scenes_have_lane=highway,
                 authored_speed_control_applicability=control_applicability,governed_speed_sign_present=posted_seen,decoder_receipt=adapter['decoder_validation'],
                 scope='Full source/camera/TrafficSpec joins; unchanged Lean-decoded artifact')
    atomic(receipt_path,receipt)
    return receipt
