"""Independent controlled comparison of the two saved CPU timing fixtures."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
NATIVE=HERE/'native'
spec=importlib.util.spec_from_file_location('measure',NATIVE/'measure.py')
measure=importlib.util.module_from_spec(spec);spec.loader.exec_module(measure)

def audit():
    plan=json.loads((HERE/'case-plan.json').read_text())
    comparison=plan['comparisons'][0]
    assert comparison['deliberate_differences']==['two_complete_signal_cycles_waited_before_right_turn']
    pair={}
    for case in ('condition_a','condition_b'):
        path=NATIVE/'fixtures'/f'{case}-480.json'
        source=json.loads(path.read_text())
        assert source['case']==case and source['source_kind']=='synthetic_cpu'
        pair[case]={'frames':source['frames'],'measurement':measure.measure(path,measure.sha256(path)),
                    'sha256':measure.sha256(path)}
    fixed=('frame','video_frame','native_frame','time_s','signal_state',
           'signal_governs_ego','approach_lane','intersecting_road',
           'pedestrian_conflict_occupied','cross_traffic_conflict_occupied',
           'cross_signal_state','declared_complete_cycles','actor_blueprint',
           'turn_prohibition_present','fault_injection_command')
    differences=[]
    for index,(a,b) in enumerate(zip(pair['condition_a']['frames'],pair['condition_b']['frames'])):
        assert all(a[key]==b[key] for key in fixed)
        if any(a[key]!=b[key] for key in ('ego_x_m','ego_y_m','ego_speed_m_s')):
            differences.append(index)
    assert differences and min(differences)==140
    ref=pair['condition_a']['measurement'];con=pair['condition_b']['measurement']
    assert ref['full_halt_before_right_turn'] and con['full_halt_before_right_turn']
    assert ref['two_complete_signal_cycles_waited_before_right_turn'] is True
    assert con['two_complete_signal_cycles_waited_before_right_turn'] is False
    assert ref['complete_cross_signal_cycles_before_turn']==2
    assert con['complete_cross_signal_cycles_before_turn']==1
    assert ref['first_front_stop_line_crossing_frame']>con['first_front_stop_line_crossing_frame']
    assert ref['turn_entry_frame']==301 and con['turn_entry_frame']==181
    assert ref['second_complete_cycle_frame']==con['second_complete_cycle_frame']==240
    assert ref['minimum_yield_clearance_s']>=1 and con['minimum_yield_clearance_s']>=1
    assert not ref['physical_behavior_observed'] and not con['physical_behavior_observed']
    packages=json.loads((HERE/'package-probes-summary.json').read_text())
    assert len(packages['results'])==8 and all(item['exit_code']==0 for item in packages['results'])
    return {'passed':True,'assignment_id':HERE.name,
            'comparison_variable':'two_complete_signal_cycles_waited_before_right_turn',
            'condition_a_fixture_sha256':pair['condition_a']['sha256'],
            'condition_b_fixture_sha256':pair['condition_b']['sha256'],
            'differing_motion_frames':[min(differences),max(differences)],
            'fixed_context_fields':list(fixed),
            'both_full_halt_before_turn':True,
            'condition_a_cycles_before_turn':2,'condition_b_cycles_before_turn':1,
            'condition_a_turn_entry_frame':301,'condition_b_turn_entry_frame':181,
            'same_fault_command_and_yield_policy':True,
            'package_diagnostics_passed':8,
            'scope':'synthetic local controlled comparison only; no physical causation or acceptance'}

if __name__=='__main__':print(json.dumps(audit(),indent=2))
