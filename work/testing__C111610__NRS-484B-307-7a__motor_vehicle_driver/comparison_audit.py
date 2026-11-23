"""Independent source-measured comparison for exact arrow cases."""
PAIRS={
 'pedestrian_crosswalk':('arrow_clear','arrow_ped_crosswalk','pedestrian','adjacent_crosswalk'),
 'pedestrian_intersection':('arrow_clear','arrow_ped_intersection','pedestrian','intersection'),
 'other_traffic_intersection':('arrow_clear','arrow_vehicle_intersection','motor_vehicle','intersection'),
 'concurrent_indication':('arrow_clear','arrow_concurrent_movement',None,None),
}
class AuditError(ValueError):
    pass

def audit(name,left,right):
    if name not in PAIRS:
        raise AuditError('unknown comparison')
    ls,rs,kind,region=PAIRS[name]
    if (left.get('case_suffix'),right.get('case_suffix'))!=(ls,rs):
        raise AuditError('wrong exact case pair')
    fixed=('map_sha256','route_source_sha256','crosswalk_source_sha256','signal_source_sha256','duration_frames','camera_profile_sha256','official_head_id','ego_approach_id')
    for key in fixed:
        if not left.get(key) or left[key]!=right.get(key):
            raise AuditError('fixed condition differs: '+key)
    for record in (left,right):
        rows=record.get('records')
        if not isinstance(rows,list) or len(rows)!=record['duration_frames']:
            raise AuditError('original frame history incomplete')
        if any('flashing_yellow_turn_arrow' not in row.get('lit_aspects',[]) for row in rows):
            raise AuditError('arrow exhibition missing')
        if any(record.get(x) is not None for x in ('lawful_presence_verdict','cautious_entry_verdict','right_of_way_verdict')):
            raise AuditError('unsupported legal verdict')
    def present(record):
        return [(u['kind'],u['region']) for row in record['records'] for u in row['other_users'] if u['region']!='outside']
    if present(left):
        raise AuditError('baseline has intersection/crosswalk participant')
    if kind is not None:
        if (kind,region) not in present(right):
            raise AuditError('required participant not observed in requested region')
        if left['concurrent_indications']!=right['concurrent_indications']:
            raise AuditError('concurrent indications changed')
        if left['ego_movement']!=right['ego_movement']:
            raise AuditError('movement changed')
    else:
        if present(right):
            raise AuditError('concurrent contrast has participant')
        if left['concurrent_indications'] or not right['concurrent_indications']:
            raise AuditError('concurrent indication contrast absent')
        if left['ego_movement']==right['ego_movement']:
            raise AuditError('movement contrast absent')
    return {'comparison_id':name,'fixed_conditions_checked':len(fixed),'source_history_checked':True,'physical_acceptance':False,'legal_verdict':None}
