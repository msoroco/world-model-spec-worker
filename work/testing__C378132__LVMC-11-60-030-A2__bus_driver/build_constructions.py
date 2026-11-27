"""Build exact inline A2 loading-stop cases with independent source gates."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
CAMERAS=[('overview',1920,1080),('approach',1280,720),('reference_corner',1280,720),('driver_reference',1280,720)]


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan=json.loads((ROOT/'case-plan.json').read_text())
    ids=[case['case_id'] for case in plan['cases']]
    common={'law_id':plan['law_id'],'cell_id':plan['cell_id'],'actor':plan['actor'],
            'candidate_id':'primary','rate_hz':20,'duration_s':45,'required_atoms':[],
            'source_packets':[],'supported_case_ids':ids,
            'cameras':[{'name':name,'width':width,'height':height,'fov_deg':75,
                        'pose_strategy':'reviewed loading place, complete bus body, signs and street context'}
                       for name,width,height in CAMERAS]}
    recording={'channels':[
        {'name':'original_bus_stop_history','unit':'s','method':'independent source-reviewed stop start/end joined to 900 Native frames','sampling_rate_hz':20,'time_window':'all 900 frames','reference_frame':'original frame/time','uncertainty':'stop interval review'},
        {'name':'designated_location_and_route','unit':'structured source','method':'official five-location designations, polygons, public-street and assigned-route source join','sampling_rate_hz':20,'time_window':'entire stop event','reference_frame':'reviewed designation','uncertainty':'authority and assigned-route review'},
        {'name':'passenger_baggage_purpose','unit':'categorical','method':'independent purpose review joined to stopped activity','sampling_rate_hz':20,'time_window':'entire stop event','reference_frame':'original source review','uncertainty':'intent review'},
        {'name':'exception_and_bus_class','unit':'categorical','method':'independent bus classification and emergency circumstances review','sampling_rate_hz':20,'time_window':'entire stop event','reference_frame':'original source review','uncertainty':'exception review'},
        {'name':'four_camera_frame_identity','unit':'frame ID','method':'four synchronized original RGB cameras','sampling_rate_hz':20,'time_window':'all 900 frames','reference_frame':'original frame/time','uncertainty':'pixel review'}],
        'context_inputs':[{'name':'reviewed_site_designation_route','unit':'structured original record','method':'source-hashed official location boundaries, jurisdiction and assigned route'},
                          {'name':'bus_operator_activity_purpose','unit':'structured original record','method':'source-hashed operator, bus class, purpose, emergency and independent stop review'}],
        'limitations':['Synthetic positions and purpose are compatibility diagnostics only; original designation, physical conduct and legal outcome remain unverified.']}
    for case in plan['cases']:
        suffix=case['case_id'].split('__')[-1]
        folder=ROOT/'cases'/suffix
        config=dict(common)
        config['selected_case_id']=case['case_id']
        config['case']={'case_id':case['case_id'],
                        **{key:case[key] for key in ('location_kind','loading_purpose','stop_reason','bus_class')},
                        'recording_description':recording}
        scene={'case_id':case['case_id'],'cell_id':'C378132','actor':'bus_driver',
               'source_kind':'synthetic_diagnostic_fixture',
               **{key:case[key] for key in ('location_kind','loading_purpose','stop_reason','bus_class')}}
        write(folder/'config.json',config);write(folder/'scene.json',scene)
        entries=[]
        for name,source in [('runner.py',ROOT/'runner.py'),('bus_location.py',ROOT/'bus_location.py'),
                            ('native_capture.py',ROOT/'native_capture.py'),
                            ('assemble_reviewed_activity.py',ROOT/'assemble_reviewed_activity.py'),
                            ('analysis.py',ROOT/'analysis.py'),('tests/test_bundle.py',ROOT/'tests/test_bundle.py'),
                            ('config.json',folder/'config.json'),('scene.json',folder/'scene.json')]:
            entries.append({'path':name,'source':str(source.relative_to(REPO)),'content':source.read_text()})
        construction={'law_id':plan['law_id'],'cell_id':plan['cell_id'],'actor':plan['actor'],
                      'case_id':case['case_id'],'entrypoint':'runner.py',
                      'recording_description':recording,'files':entries,
                      'measurement_plan':{'bus_identity':'source-hashed operator and regular/tour bus class',
                       'official_locations':'City Traffic Engineer stop, stand, passenger zone and assigned-route endpoint boundaries',
                       'activity_interval':'independent stopped interval joined to original 900 Native frames',
                       'loading_purpose':'independent passenger, baggage or cargo-only purpose review',
                       'emergency':'independent ordinary or emergency circumstance review',
                       'body_position':'actual footprint relative to all permitted polygons over the complete stop'},
                      'static_checks':['exact C378132 selected case/config','reviewed original street, five locations, route and designation SHA-256 before Native spawn','900 synchronized original frames and four cameras'],
                      'termination_rules':['stop at 900 Native ticks','fail on incomplete stop interval or body/camera source mismatch'],
                      'mechanisms':['reviewed business-district street and five official location polygons','bus approach, controlled halt and departure at selected location','source-reviewed purpose, tour status and emergency circumstances','four synchronized RGB cameras and Native bus footprint samples']}
        write(folder/'construction.json',construction)
    for name in ('config.json','scene.json','construction.json'):
        (ROOT/name).write_text((ROOT/'cases/outside_passenger'/name).read_text())
    print(f"{len(ids)} exact source-gated inline bus constructions generated")


if __name__=='__main__':build()
