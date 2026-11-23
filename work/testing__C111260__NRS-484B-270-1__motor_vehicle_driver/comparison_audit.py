"""Independent fixed-condition and source-completeness check for exact cases."""
from __future__ import annotations

class ComparisonError(ValueError):
    pass

def audit(left,right):
    expected=('maintain_clearance','cross_rider_path')
    if (left.get('mode'),right.get('mode'))!=expected:
        raise ComparisonError('wrong exact mode pair')
    fixed=('map_sha256','bicycle_classification_sha256','rider_rules_sha256','ego_route_sha256','rider_route_sha256','camera_profile_sha256','duration_frames','ego_blueprint_id','bicycle_blueprint_id')
    for key in fixed:
        if not left.get(key) or left[key]!=right.get(key):
            raise ComparisonError('fixed condition missing or differs: '+key)
    for record in (left,right):
        if record.get('frame_count')!=record['duration_frames']:
            raise ComparisonError('incomplete Original history')
        if not record.get('original_sources') or not record.get('visual_rider_witness'):
            raise ComparisonError('original classification/visual source missing')
        if record.get('lawful_riding_verdict') is not None or record.get('intent_verdict') is not None or record.get('interference_verdict') is not None:
            raise ComparisonError('unsupported legal verdict supplied')
    if left.get('waiting_command_frames',0)<=0 or right.get('travel_command_frames',0)<=0:
        raise ComparisonError('commanded behavior difference not evidenced')
    return {'comparison_id':'bicycle_encounter_behavior','fixed_conditions_checked':len(fixed),'legal_verdict':None,'physical_acceptance':False}
