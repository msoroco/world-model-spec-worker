"""Independent checks of authored geometry, candidate isolation and saved timing."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).parent
NATIVE=ROOT/'native'

def load(name: str):
    spec=importlib.util.spec_from_file_location(name,NATIVE/f'{name}.py')
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def audit() -> dict:
    geom=load('geometry')
    eng=load('engineering')
    meas=load('measure')
    assignment=json.loads((ROOT.parent.parent/'inputs'/ROOT.name/'assignment.json').read_text())
    contract=json.loads((NATIVE/'measurement-contract.json').read_text())
    plan=json.loads((NATIVE/'engineering-plan.json').read_text())
    assert assignment['cell']['layout']=='intersection'
    assert assignment['cell']['maneuver']=='right_turn'
    assert assignment['cell']['control']=='traffic_light'
    assert assignment['law_record']['id']=='NRS-484B-307-8c'
    assert 'After complying with the requirement to stop' in assignment['law_record']['text']
    assert contract['assignment_id']==assignment['assignment_id']
    assert contract['frame_contract']['frames']==480 and contract['frame_contract']['rate_hz']==20
    assert plan['assignment_id']==assignment['assignment_id']
    assert plan['candidates']==[eng.parameters(case,candidate)
                                for case in eng.CASES for candidate in eng.CANDIDATES]
    xml=ET.parse(NATIVE/'road.xodr').getroot()
    roads={int(r.attrib['id']):r for r in xml.findall('road')}
    assert set(roads)=={1,2,3,4,13,14}
    assert roads[13].find('planView/geometry/arc') is not None
    assert roads[13].find('link/predecessor').attrib['elementId']=='1'
    assert roads[13].find('link/successor').attrib['elementId']=='2'
    assert len(xml.findall(".//signal[@id='601']"))==1
    assert roads[14].find('planView/geometry/line') is not None
    assert roads[14].find('link/predecessor').attrib['elementId']=='3'
    assert roads[14].find('link/successor').attrib['elementId']=='2'
    assert len(xml.findall(".//signal[@id='602']"))==1
    assert len(xml.findall(".//object[@type='crosswalk']"))==2
    assert len(xml.findall(".//object[@name='nearest-side-crosswalk']"))==1
    assert len(xml.findall(".//object[@name='destination-pedestrian-crosswalk']"))==1
    assert len(xml.findall(".//object[@name='stop-line']"))==1
    assert geom.STOP_LINE_Y_M<geom.CROSSWALK_NEAR_Y_M<geom.INTERSECTION_NEAR_Y_M
    assert json.loads((NATIVE/'route.json').read_text())==geom.route()
    assert (NATIVE/'road.xodr').read_text()==geom.open_drive()
    assert geom.check()['passed']
    pair=[]
    for case in eng.CASES:
        choices=[eng.parameters(case,c) for c in eng.CANDIDATES]
        assert [p['candidate'] for p in choices]==list(eng.CANDIDATES)
        assert len({json.dumps(p['knobs'],sort_keys=True) for p in choices})==4
        for p in choices[1:]:
            changed={k for k,v in p['knobs'].items() if v!=choices[0]['knobs'][k]}
            assert len(changed)==1
        for p in choices:
            assert p['knobs']['rate_hz']==20 and p['knobs']['duration_s']==24.0
            assert p['law_id']=='NRS-484B-307-8c' and p['cell_id']=='C110919'
            assert p['comparison_variable']=='halt_before_right_turn_on_red'
            assert p['yield_command']=='wait_for_pedestrian_clearance'
        path=NATIVE/'fixtures'/f'{case}-480.json'
        result=meas.measure(path,meas.sha256(path))
        assert result['case']==case and result['frames']==480
        assert result['yield_clearance_s']>=1.0 and not result['physical_behavior_observed']
        pair.append(result)
    assert pair[0]['halt_before_right_turn_on_red'] is True
    assert pair[1]['halt_before_right_turn_on_red'] is False
    assert pair[0]['pre_crossing_stationary_frames_contiguous']>=10
    assert pair[1]['pre_crossing_stationary_frames_contiguous']==0
    a=json.loads((NATIVE/'fixtures'/'probe_a-480.json').read_text())['frames']
    b=json.loads((NATIVE/'fixtures'/'probe_b-480.json').read_text())['frames']
    for left,right in zip(a,b):
        for key in ('signal_state','signal_governs_ego','approach_lane',
                    'intersecting_road','pedestrian_conflict_occupied','ego_turn_entered'):
            assert left[key]==right[key]
    # Negative fixtures prove the saved checker rejects source mismatches and
    # missing required context instead of merely accepting a nominal trace.
    with tempfile.TemporaryDirectory() as temp:
        good=NATIVE/'fixtures'/'probe_a-480.json'
        bad=Path(temp)/'bad.json'
        modified=json.loads(good.read_text())
        modified['frames'][0]['signal_state']='green'
        bad.write_text(json.dumps(modified))
        try:
            meas.measure(bad,meas.sha256(bad))
        except ValueError as exc:
            assert 'signal' in str(exc)
        else:
            raise AssertionError('Negative signal fixture accepted')
        try:
            meas.measure(good,'0'*64)
        except ValueError as exc:
            assert 'Source bytes' in str(exc)
        else:
            raise AssertionError('Wrong source hash accepted')
        metrics={'source_kind':'original_native_and_video',
                 'max_route_cross_track_error_m':.5,
                 'min_pedestrian_clearance_s':.5,
                 'min_signal_or_body_pixel_margin_px':30}
        source=Path(temp)/'metrics.json'
        source.write_text(json.dumps(metrics))
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        assert all(eng.evaluate_trigger(c,metrics,source,digest) for c in eng.CANDIDATES[1:])
        for c in eng.CANDIDATES[1:]:
            try:
                eng.evaluate_trigger(c,metrics,source,'0'*64)
            except ValueError:
                pass
            else:
                raise AssertionError('Unbound trigger accepted')
            for invalid in (float('nan'), float('inf'), -float('inf'), True):
                altered = dict(metrics, **{eng.TRIGGERS[c]['metric']: invalid})
                source.write_text(json.dumps(altered))
                try:
                    eng.evaluate_trigger(c, altered, source,
                                         hashlib.sha256(source.read_bytes()).hexdigest())
                except ValueError:
                    pass
                else:
                    raise AssertionError('Nonfinite or boolean trigger accepted')
            source.write_text(json.dumps(metrics))
    return {'passed':True,'assignment_id':ROOT.name,'source_scope':'authored CPU geometry and synthetic saved frames',
            'candidate_count':8,'pair_variable':'halt_before_right_turn_on_red',
            'synthetic_pair':pair,'negative_checks':['signal_state','source_hash','fallback_source_hash'],
            'native_map_readback':False,'original_video':False,'accepted_recording':False}

if __name__=='__main__':
    print(json.dumps(audit(),indent=2))
