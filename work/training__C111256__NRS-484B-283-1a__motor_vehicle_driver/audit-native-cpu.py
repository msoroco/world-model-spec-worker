"""Independent authored Native and circular-green synthetic CPU audit."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent
NATIVE=HERE/'native'
def module(name):
    spec=importlib.util.spec_from_file_location(name,NATIVE/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def audit():
    source=json.loads((HERE.parent.parent/'inputs'/HERE.name/'assignment.json').read_text())
    geom=module('geometry');eng=module('engineering');meas=module('measure')
    assert source['law_record']['id']=='NRS-484B-283-1a'
    assert source['cell']['maneuver']=='right_turn' and source['cell']['control']=='traffic_light'
    assert 'circular green alone' in source['law_record']['text']
    assert 'unless another device' in source['law_record']['text']
    assert 'must yield the right-of-way' in source['law_record']['text']
    assert geom.check()['passed']
    assert (NATIVE/'road.xodr').read_text()==geom.open_drive()
    assert json.loads((NATIVE/'route.json').read_text())==geom.route()
    xml=ET.parse(NATIVE/'road.xodr').getroot()
    assert len(xml.findall(".//signal[@id='601']"))==1
    assert len(xml.findall(".//object[@type='crosswalk']"))==2
    plan=json.loads((NATIVE/'engineering-plan.json').read_text())
    assert plan['candidates']==[eng.parameters(c,k) for c in eng.CASES for k in eng.CANDIDATES]
    pair=[]
    for case in eng.CASES:
        candidates=[eng.parameters(case,k) for k in eng.CANDIDATES]
        assert len({json.dumps(x['knobs'],sort_keys=True) for x in candidates})==4
        for x in candidates[1:]:
            assert sum(x['knobs'][k]!=candidates[0]['knobs'][k] for k in candidates[0]['knobs'])==1
        path=NATIVE/'fixtures'/(case+'-480.json')
        result=meas.measure(path,meas.sha256(path))
        assert result['circular_green_frames']==480 and result['turn_prohibition_absent']
        assert not result['physical_behavior_observed'] and result['legal_verdict'] is None
        pair.append(result)
    assert [x['yielded_to_lawful_users'] for x in pair]==[True,False]
    assert [x['turn_entry_frame'] for x in pair]==[181,145]
    assert [x['last_pedestrian_conflict_frame'] for x in pair]==[160,160]
    assert [x['last_cross_traffic_conflict_frame'] for x in pair]==[160,160]
    a=json.loads((NATIVE/'fixtures/witness_1-480.json').read_text())['frames']
    b=json.loads((NATIVE/'fixtures/witness_2-480.json').read_text())['frames']
    for x,y in zip(a,b):
        for k in ('frame','time_s','signal_state','signal_governs_ego','turn_prohibition_present',
                  'approach_lane','intersecting_road','pedestrian_conflict_occupied',
                  'cross_traffic_conflict_occupied'):
            assert x[k]==y[k]
    with tempfile.TemporaryDirectory() as temp:
        bad=Path(temp)/'bad.json';modified=json.loads((NATIVE/'fixtures/witness_1-480.json').read_text())
        modified['frames'][0]['signal_state']='steady_red';bad.write_text(json.dumps(modified))
        try:meas.measure(bad,meas.sha256(bad))
        except ValueError as exc:assert 'green' in str(exc)
        else:raise AssertionError('Wrong signal accepted')
        metrics={'source_kind':'original_native_and_video','max_route_cross_track_error_m':.5,
                 'min_lawful_user_clearance_s':.5,'min_signal_or_body_pixel_margin_px':30}
        path=Path(temp)/'metrics.json';path.write_text(json.dumps(metrics));digest=hashlib.sha256(path.read_bytes()).hexdigest()
        assert all(eng.evaluate_trigger(k,metrics,path,digest) for k in eng.CANDIDATES[1:])
        for k in eng.CANDIDATES[1:]:
            try:eng.evaluate_trigger(k,metrics,path,'0'*64)
            except ValueError:pass
            else:raise AssertionError('Unbound trigger accepted')
    return {'passed':True,'assignment_id':HERE.name,'candidate_count':8,
            'comparison_variable':'yielded_to_lawful_users','pair':pair,
            'scope':'authored Native proposal and synthetic CPU only; no physical or accepted recording'}
if __name__=='__main__':print(json.dumps(audit(),indent=2))
