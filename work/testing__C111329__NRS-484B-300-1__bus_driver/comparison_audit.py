"""Independent source/condition audit for an attempted device-instruction contrast."""
from __future__ import annotations

class AuditError(ValueError):
    pass

def audit_pair(left, right, difference):
    required = ('map_sha256','device_sha256','route_sha256','authority_sha256','bus_blueprint_id',
                'camera_profile','duration_s','device_id','facing_approach_id')
    for key in required:
        if not left.get(key) or not right.get(key) or left[key] != right[key]:
            raise AuditError('fixed source/condition missing or changed: '+key)
    if difference not in ('bus_line_behavior','police_direction','device_instruction'):
        raise AuditError('unreviewed comparison variable')
    if difference == 'bus_line_behavior':
        if left.get('police_direction') != right.get('police_direction') or left.get('aspect') != right.get('aspect'):
            raise AuditError('context changed in conduct comparison')
        if left.get('line_entry') == right.get('line_entry') or None in (left.get('line_entry'),right.get('line_entry')):
            raise AuditError('original line-crossing difference missing')
    elif difference == 'police_direction':
        if left.get('aspect') != right.get('aspect') or left.get('line_entry') != right.get('line_entry'):
            raise AuditError('conduct/device changed in police comparison')
        if left.get('police_direction') == right.get('police_direction') or not right.get('police_direction_source'):
            raise AuditError('source-backed police direction difference missing')
    else:
        if left.get('line_entry') != right.get('line_entry') or left.get('police_direction') != right.get('police_direction'):
            raise AuditError('conduct or police context changed in device comparison')
        if (left.get('aspect'), right.get('aspect')) != ('red', 'green'):
            raise AuditError('original red/green instruction difference missing')
    for row in (left,right):
        if not row.get('placement_source') or not row.get('nrs_307_context_source') or not row.get('original_trace_sha256'):
            raise AuditError('missing original device/exception/trace evidence')
    return {'comparison_variable':difference,'accepted_as_source_complete':True,'legal_verdict':None}

def audit_delivery(measured, expected_case):
    """Reject an incomplete saved attempt without assigning a legal conclusion."""
    frames=measured.get('frames')
    if not isinstance(frames,list) or len(frames)<3:
        raise AuditError('missing original device/bus frame history')
    required=('device_id','facing_approach_id','bus_blueprint_id','map_sha256',
              'device_sha256','route_sha256','authority_sha256','original_trace_sha256',
              'four_view_video_sha256','duration_s','placement_source','nrs_307_context_source')
    for key in required:
        if not measured.get(key):
            raise AuditError('missing delivery evidence: '+key)
    if measured.get('case_id')!=expected_case['case_id']:
        raise AuditError('wrong exact case')
    if measured['duration_s']!=expected_case['duration_s']:
        raise AuditError('duration mismatch')
    if any(a['frame']>=b['frame'] for a,b in zip(frames,frames[1:])):
        raise AuditError('nonmonotone original frames')
    if any(r['aspect']!=expected_case['device_aspect'] for r in frames):
        raise AuditError('governing aspect changed')
    crossing=any(r['bus_front_signed_distance_m']<0 for r in frames)
    if crossing != expected_case['line_entry']:
        raise AuditError('observed line entry differs from expected case construction')
    if expected_case.get('police_direction')=='proceed' and not measured.get('police_direction_source'):
        raise AuditError('missing contemporaneous police direction source')
    return {'case_id':expected_case['case_id'],'source_complete':True,'observed_line_entry':crossing,
            'legal_verdict':None,'physical_visibility_verdict':None}
