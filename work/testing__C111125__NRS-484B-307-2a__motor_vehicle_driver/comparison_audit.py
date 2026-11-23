"""Independent exact-case comparison over source-measured attempt summaries."""
PAIRS={
 'intersection_vehicle_yield':('green_clear','green_vehicle_present',None,'intersection'),
 'crosswalk_pedestrian_yield':('green_clear','green_pedestrian_present',None,'adjacent_crosswalk'),
 'exhibition_time_qualification':('green_pedestrian_present','green_pedestrian_late','adjacent_crosswalk','outside'),
}
class ComparisonError(ValueError):
    pass

def audit_pair(name,left,right):
    if name not in PAIRS:
        raise ComparisonError('unknown comparison')
    ls,rs,lreg,rreg=PAIRS[name]
    if (left.get('case_suffix'),right.get('case_suffix'))!=(ls,rs):
        raise ComparisonError('wrong exact case pair')
    fixed=('map_sha256','signal_source_sha256','route_source_sha256','crosswalk_source_sha256','camera_profile_sha256','duration_frames','official_head_id','ego_approach_id')
    for key in fixed:
        if not left.get(key) or left[key]!=right.get(key):
            raise ComparisonError('fixed condition differs: '+key)
    for record,region in ((left,lreg),(right,rreg)):
        if record.get('green_frames')!=record['duration_frames']:
            raise ComparisonError('circular green alone not evidenced throughout')
        exhibition=record.get('exhibition')
        if not exhibition or not isinstance(exhibition.get('other_users'),list):
            raise ComparisonError('original exhibition user positions missing')
        regions=[p['region'] for p in exhibition['other_users']]
        if region is None and regions:
            raise ComparisonError('clear baseline occupied at exhibition')
        if region is not None and regions!=[region]:
            raise ComparisonError('other user region at exhibition differs')
        if record.get('lawful_presence_verdict') is not None or record.get('right_of_way_verdict') is not None:
            raise ComparisonError('unsupported legal verdict supplied')
    return {'comparison_id':name,'fixed_conditions_checked':len(fixed),'exhibition_checked':True,'physical_acceptance':False,'legal_verdict':None}
