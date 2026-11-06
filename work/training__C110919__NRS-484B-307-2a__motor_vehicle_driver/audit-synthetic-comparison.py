"""Independent controlled pair audit for circular-green lawful-user yield."""
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
NATIVE=HERE/'native'
def audit():
    import sys
    sys.path.insert(0,str(NATIVE))
    import measure
    plan=json.loads((HERE/'case-plan.json').read_text())
    comparison=plan['comparisons'][0]
    assert comparison['deliberate_differences']==['yielded_to_lawful_users']
    pair={}
    for case in ('controlled_1','controlled_2'):
        path=NATIVE/'fixtures'/(case+'-480.json')
        pair[case]={'rows':json.loads(path.read_text())['frames'],
                    'measure':measure.measure(path,measure.sha256(path)),'sha256':measure.sha256(path)}
    a=pair['controlled_1'];b=pair['controlled_2']
    for left,right in zip(a['rows'],b['rows']):
        for key in ('frame','time_s','signal_state','signal_governs_ego',
                    'turn_prohibition_present','approach_lane','intersecting_road',
                    'pedestrian_conflict_occupied','cross_traffic_conflict_occupied'):
            assert left[key]==right[key]
    am=a['measure'];bm=b['measure']
    assert am['yielded_to_lawful_users'] is True and bm['yielded_to_lawful_users'] is False
    assert am['turn_entry_frame']==181 and bm['turn_entry_frame']==145
    assert am['yield_clearance_s']==1.05 and bm['yield_clearance_s']==-.75
    assert am['circular_green_frames']==bm['circular_green_frames']==480
    packages=json.loads((HERE/'package-probes-summary.json').read_text())
    assert len(packages['results'])==8 and all(r['exit_code']==0 for r in packages['results'])
    return {'passed':True,'assignment_id':HERE.name,'comparison_variable':'yielded_to_lawful_users',
            'reference_sha256':a['sha256'],'contrast_sha256':b['sha256'],
            'reference_turn_frame':181,'contrast_turn_frame':145,'shared_conflict_end_frame':160,
            'package_diagnostics_passed':8,'scope':'synthetic local comparison only; no physical acceptance'}
if __name__=='__main__':print(json.dumps(audit(),indent=2))
