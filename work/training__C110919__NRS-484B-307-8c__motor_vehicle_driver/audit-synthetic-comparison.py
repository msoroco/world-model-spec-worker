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
    assert comparison['deliberate_differences']==['halt_before_right_turn_on_red']
    pair={}
    for case in ('probe_a','probe_b'):
        path=NATIVE/'fixtures'/f'{case}-480.json'
        source=json.loads(path.read_text())
        assert source['case']==case and source['source_kind']=='synthetic_cpu'
        pair[case]={'frames':source['frames'],'measurement':measure.measure(path,measure.sha256(path)),
                    'sha256':measure.sha256(path)}
    fixed=('frame','video_frame','native_frame','time_s','signal_state',
           'signal_governs_ego','approach_lane','intersecting_road',
           'pedestrian_conflict_occupied','ego_turn_entered')
    differences=[]
    for index,(a,b) in enumerate(zip(pair['probe_a']['frames'],pair['probe_b']['frames'])):
        assert all(a[key]==b[key] for key in fixed)
        if any(a[key]!=b[key] for key in ('ego_x_m','ego_y_m','ego_speed_m_s')):
            differences.append(index)
    assert differences and min(differences)>=100 and max(differences)<170
    ref=pair['probe_a']['measurement'];con=pair['probe_b']['measurement']
    assert ref['halt_before_right_turn_on_red'] is True
    assert con['halt_before_right_turn_on_red'] is False
    assert ref['first_front_stop_line_crossing_frame']>con['first_front_stop_line_crossing_frame']
    assert ref['turn_entry_frame']==con['turn_entry_frame']==181
    assert ref['yield_clearance_s']==con['yield_clearance_s']==1.05
    assert not ref['physical_behavior_observed'] and not con['physical_behavior_observed']
    packages=json.loads((HERE/'package-probes-summary.json').read_text())
    assert len(packages['results'])==8 and all(item['exit_code']==0 for item in packages['results'])
    return {'passed':True,'assignment_id':HERE.name,
            'comparison_variable':'halt_before_right_turn_on_red',
            'probe_a_fixture_sha256':pair['probe_a']['sha256'],
            'probe_b_fixture_sha256':pair['probe_b']['sha256'],
            'differing_motion_frames':[min(differences),max(differences)],
            'fixed_context_fields':list(fixed),
            'probe_a_stop':ref['halt_before_right_turn_on_red'],
            'probe_b_stop':con['halt_before_right_turn_on_red'],
            'same_turn_entry_frame':181,'same_yield_clearance_s':1.05,
            'package_diagnostics_passed':8,
            'scope':'synthetic local controlled comparison only; no physical causation or acceptance'}

if __name__=='__main__':print(json.dumps(audit(),indent=2))
