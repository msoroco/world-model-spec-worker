"""Independent measured-result comparison for NRS 484B.307(4)(b) pairs."""
from __future__ import annotations

PAIRS = {
 'entry_without_other_permission':('arrow_wait','arrow_early_entry',False,False,False,True),
 'separate_device_permission':('arrow_early_entry','arrow_walk_entry',False,True,True,True),
 'permitted_entry_choice':('arrow_walk_wait','arrow_walk_entry',True,True,False,True),
}

class ComparisonError(ValueError):
    pass


def audit_pair(comparison_id, left, right):
    if comparison_id not in PAIRS:
        raise ComparisonError('unknown comparison')
    l_name,r_name,l_walk,r_walk,l_entry,r_entry=PAIRS[comparison_id]
    if (left.get('case_suffix'),right.get('case_suffix'))!=(l_name,r_name):
        raise ComparisonError('wrong exact case pair')
    for key in ('map_source_sha256','vehicle_signal_source_sha256','highway_boundary_source_sha256','pedestrian_route_source_sha256','camera_profile_sha256','duration_frames'):
        if not left.get(key) or left[key]!=right.get(key):
            raise ComparisonError('fixed condition differs: '+key)
    for row,walk,entry in ((left,l_walk,l_entry),(right,r_walk,r_entry)):
        if row.get('sole_green_arrow_frames')!=row['duration_frames']:
            raise ComparisonError('sole green arrow not evidenced throughout')
        measured=row.get('first_highway_entry')
        if (measured is not None)!=entry:
            raise ComparisonError('entry difference not realized')
        if measured is not None:
            if measured.get('separate_walk_indication') is not walk:
                raise ComparisonError('separate device state at entry differs')
        elif row.get('separate_walk_indication_without_entry') is not walk:
            raise ComparisonError('separate device state while waiting differs')
    return {'comparison_id':comparison_id,'measured_pair':[l_name,r_name],
            'fixed_conditions_checked':6,'arrow_frames_checked':left['duration_frames']+right['duration_frames'],
            'physical_acceptance':False,'legal_verdict':None}
