"""Build exact inline bus-stop position cases with independent source gates."""
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
                        'pose_strategy':'reviewed stop, complete bus body, signs and street context'}
                       for name,width,height in CAMERAS]}
    recording={'channels':[
        {'name':'bus_stopped_interval','unit':'s','method':'independent source-reviewed activity start/end joined to 900 Native frames','sampling_rate_hz':20,'time_window':'all 900 frames','reference_frame':'original frame/time','uncertainty':'standing/parking conduct review'},
        {'name':'designated_stop_and_alternatives','unit':'structured source','method':'official stop, signs, public-street and other permitted-location source join','sampling_rate_hz':20,'time_window':'entire stop event','reference_frame':'reviewed designation','uncertainty':'authority and assigned-route review'},
        {'name':'body_inside_stop','unit':'bool','method':'Native bus-body corners against reviewed stop polygon','sampling_rate_hz':20,'time_window':'all 900 frames','reference_frame':'original frame/time','uncertainty':'body and boundary localization'},
        {'name':'four_camera_frame_identity','unit':'frame ID','method':'four synchronized original RGB cameras','sampling_rate_hz':20,'time_window':'all 900 frames','reference_frame':'original frame/time','uncertainty':'pixel review'}],
        'context_inputs':[{'name':'reviewed_site_and_designation','unit':'structured original record','method':'source-hashed signed official stop boundary, jurisdiction, route termini and other permissible locations'},
                          {'name':'bus_operator_and_activity','unit':'structured original record','method':'source-hashed non-tour bus/operator and independent conduct review'}],
        'limitations':['Synthetic boundary and bus position are compatibility diagnostics only; original designation and legal outcome remain unverified.']}
    for case in plan['cases']:
        suffix=case['case_id'].split('__')[-1]
        folder=ROOT/'cases'/suffix
        config=dict(common)
        config['selected_case_id']=case['case_id']
        config['case']={'case_id':case['case_id'],'conduct':case['conduct'],
                        'location_relation':case['location_relation'],'recording_description':recording}
        scene={'case_id':case['case_id'],'cell_id':'C378132','actor':'bus_driver',
               'source_kind':'synthetic_diagnostic_fixture','conduct':case['conduct'],
               'location_relation':case['location_relation']}
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
                      'measurement_plan':{'bus_identity':'source-hashed covered non-tour bus and assigned route',
                       'official_stop':'signed City Traffic Engineer stop boundary and alternatives',
                       'activity_interval':'independent standing/parking start/end joined to original 900 Native frames',
                       'body_position':'actual footprint inside or outside official stop polygon over full activity'},
                      'static_checks':['exact C378132 selected case/config','reviewed original street, stop, route and designation SHA-256 before Native spawn','900 synchronized original frames and four cameras'],
                      'termination_rules':['stop at 900 Native ticks','fail on incomplete stopped interval or body/camera source mismatch'],
                      'mechanisms':['reviewed one-way street and designated bus-stop polygon','non-tour bus approach, controlled halt and departure at selected inside or outside pose','source-reviewed alternative permissible locations','four synchronized RGB cameras and Native bus footprint samples']}
        write(folder/'construction.json',construction)
    for name in ('config.json','scene.json','construction.json'):
        (ROOT/name).write_text((ROOT/'cases/stand_inside'/name).read_text())
    print('four exact source-gated inline bus constructions generated')


if __name__=='__main__':build()
