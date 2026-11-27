"""Source-bound vehicle-front versus lawful-traffic direction measurement."""
from __future__ import annotations
import math

def finite(value,label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('finite '+label+' required')
    return float(value)

def unit(vector):
    if not isinstance(vector,list) or len(vector)!=2:raise ValueError('original lawful direction vector required')
    x,y=[finite(v,'lawful vector component') for v in vector];size=math.hypot(x,y)
    if size<.01:raise ValueError('original lawful direction vector degenerate')
    return x/size,y/size

def measure(packet):
    if not isinstance(packet,dict) or packet.get('source_kind') not in {'original_native','diagnostic_native_shape'}:
        raise ValueError('original Native or explicit diagnostic source required')
    diagnostic=packet['source_kind']=='diagnostic_native_shape'
    if diagnostic and packet.get('diagnostic_fixture') is not True:raise ValueError('diagnostic provenance required')
    for key in ('assignment_id','case_id','capture_source_sha256','marking_source_sha256','frame_map_sha256'):
        if not isinstance(packet.get(key),str) or not packet[key]:raise ValueError('missing source binding: '+key)
    if packet['assignment_id']!='testing__C377875__LVMC-11-52-070__motor_vehicle_driver' or not packet['case_id'].startswith(packet['assignment_id']+'__'):
        raise ValueError('exact assignment or case differs')
    marking=packet.get('marking',{});authority=packet.get('authority',{})
    if (marking.get('marking_status')!='reviewed_original' or marking.get('permission_indicated') is not True
        or authority.get('determining_office')!='City Traffic Engineer' or authority.get('permission_status')!='reviewed_original'
        or authority.get('angle_parking_permitted') is not True):raise ValueError('original Engineer permission and marking required')
    if packet.get('roadway_source_review')!='reviewed_original' or packet.get('lawful_direction_status')!='reviewed_original':
        raise ValueError('original roadway and lawful direction review required')
    if packet.get('purpose_review',{}).get('activity_review')!='reviewed_original':raise ValueError('original stand/park purpose review required')
    lawful=unit(packet.get('lawful_traffic_vector_xy'));frames=packet.get('frames')
    if not isinstance(frames,list) or not frames:raise ValueError('original frame history required')
    expected=frames[0].get('frame');angles=[];front_dots=[];halt=[]
    if isinstance(expected,bool) or not isinstance(expected,int):raise ValueError('invalid original frame identity')
    for row in frames:
        if row.get('frame')!=expected:raise ValueError('noncontiguous original frame history')
        expected+=1
        if row.get('halt_observed') is True:
            yaw=math.radians(finite(row.get('body_yaw_degrees'),'vehicle front yaw'))
            dot=math.cos(yaw)*lawful[0]+math.sin(yaw)*lawful[1]
            angles.append(math.degrees(math.acos(max(-1,min(1,dot)))))
            front_dots.append(dot);halt.append(row['frame'])
        elif row.get('halt_observed') is not False:raise ValueError('halt observation missing')
    if len(halt)<2:raise ValueError('two observed standing/parking frames required')
    return {'format':'worker-lawful-traffic-orientation-measurement','assignment_id':packet['assignment_id'],
            'case_id':packet['case_id'],'source_bindings':{k:packet[k] for k in ('capture_source_sha256','marking_source_sha256','frame_map_sha256')},
            'diagnostic_fixture':diagnostic,'halt_first_frame':halt[0],'halt_last_frame':halt[-1],
            'halt_frame_count':len(halt),'front_vs_lawful_direction_min_degrees':min(angles),
            'front_vs_lawful_direction_max_degrees':max(angles),
            'front_vs_lawful_direction_mean_degrees':sum(angles)/len(angles),
            'front_dot_lawful_direction_mean':sum(front_dots)/len(front_dots),
            'legal_classification':'unreviewed','physical_original_review':'pending'}
