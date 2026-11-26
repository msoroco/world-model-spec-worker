"""Independent measured-result comparison for NRS 484B.307(4)(b) pairs."""
from __future__ import annotations

PAIRS = {
 'entry_without_other_permission':('arrow_wait','arrow_early_entry',False,False,False,True),
 'separate_device_permission':('arrow_early_entry','arrow_walk_entry',False,True,True,True),
 'permitted_entry_choice':('arrow_walk_wait','arrow_walk_entry',True,True,False,True),
}

CITED_PAIRS = {
 'cited_applicability_1d1_1d2': ('permission_applicability-0000','permission_applicability-0001','NRS-484B-283-1d1','NRS-484B-283-1d2',1.0,4.0),
 'cited_applicability_1d2_1d3': ('permission_applicability-0001','permission_applicability-0002','NRS-484B-283-1d2','NRS-484B-283-1d3',4.0,2.0),
 'cited_applicability_1d3_1d4': ('permission_applicability-0002','permission_applicability-0003','NRS-484B-283-1d3','NRS-484B-283-1d4',2.0,3.0),
}

class ComparisonError(ValueError):
    pass


def audit_pair(comparison_id, left, right):
    if comparison_id in CITED_PAIRS:
        return audit_cited_pair(comparison_id,left,right)
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


def audit_cited_pair(comparison_id, left, right):
    left_suffix,right_suffix,left_provision,right_provision,left_delay,right_delay=CITED_PAIRS[comparison_id]
    if (left.get('case_suffix'),right.get('case_suffix'))!=(left_suffix,right_suffix):
        raise ComparisonError('wrong exact cited applicability case pair')
    for key in ('map_source_sha256','vehicle_signal_source_sha256','highway_boundary_source_sha256','pedestrian_route_source_sha256','pedestrian_device_source_sha256','camera_profile_sha256','duration_frames'):
        if not left.get(key) or left[key]!=right.get(key):
            raise ComparisonError('fixed condition differs: '+key)
    for row,provision,delay in ((left,left_provision,left_delay),(right,right_provision,right_delay)):
        if row.get('focus_provision_id')!=provision or row.get('entry_delay_s')!=delay:
            raise ComparisonError('cited provision or authored entry hold differs')
        entry=row.get('first_highway_entry')
        if not isinstance(entry,dict) or entry.get('separate_walk_indication') is not True:
            raise ComparisonError('original entry and separate WALK not measured')
        if row.get('sole_green_arrow_frames')!=row['duration_frames'] or row.get('first_highway_entry_time_s')!=entry['frame']/20:
            raise ComparisonError('source measured timing differs')
        if entry['frame']<delay*20:
            raise ComparisonError('original entry precedes authored hold')
        if row.get('diagnostic_fixture') is False and not row.get('review_disposition'):
            raise ComparisonError('original cited applicability review missing')
    if left['first_highway_entry_time_s']==right['first_highway_entry_time_s']:
        raise ComparisonError('cited sweep timing difference not realized')
    return {'comparison_id':comparison_id,'measured_pair':[left_suffix,right_suffix],
            'cited_provisions':[left_provision,right_provision],
            'focus_applicability':[left.get('review_disposition'),right.get('review_disposition')],
            'measured_entry_time_s':[left['first_highway_entry_time_s'],right['first_highway_entry_time_s']],
            'fixed_conditions_checked':7,'physical_acceptance':False,'legal_verdict':None}
