"""Generate the canonical first exact roundabout Native request."""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRATCH = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
AID = 'training__C132924__NRS-484B-627-1b__motor_vehicle_driver'
SUFFIXES = ('probe_a','probe_b','necessary_pass','post_pass_linger')
NAMES = ('overview','approach','reference_corner','driver_reference')
SIZES = ((1920,1080),(1280,720),(1280,720),(1280,720))
FOV = (85,90,85,90)


def build(suffix):
    case_id = AID+'__'+suffix
    source_terms = {
        'drv.speed_below_traffic':'Original ego and immediately following vehicle speeds by Native frame',
        'drv.queue_behind':'Original immediately following vehicle identity and position by Native frame',
        'drv.laned_roadway':'Original marked same-direction Native roundabout lane survey and readback',
        'drv.extreme_lane':'Original extreme-right lane boundary and ego body vertices by Native frame',
        'rel.occupies':'Original ego body occupancy against surveyed lane boundaries by Native frame',
        'drv.overtaking':'Original slower vehicle, relative motion and clearance by Native frame',
        'st.lane_adjacency':'Original adjacent same-direction lane topology from Native map and survey'}
    description = {
        'channels': [
            {'name':'native_lane_body_follower_and_pass',
             'method':'Original Native 20-Hz map lane, ego body, immediate follower, slower vehicle and pass clearance',
             'sampling_rate_hz':20,'time_window':'600 frames','unit':'structured',
             'reference_frame':'original Native frame joined to four-camera frame map',
             'uncertainty':'impeding and passing necessity are independent legal judgments'},
            {'name':'four_camera_video','method':'Four synchronized original RGB views',
             'sampling_rate_hz':20,'time_window':'600 frames','unit':'structured',
             'reference_frame':'original Native frame joined to four-camera frame map',
             'uncertainty':'software fixture cannot prove original pixel visibility'}] + [
            {'name':name,'method':method,'sampling_rate_hz':20,'time_window':'600 frames',
             'unit':'structured','reference_frame':'original Native frame joined to four-camera frame map',
             'uncertainty':'Source facts do not settle statutory impeding or passing necessity'}
            for name,method in source_terms.items()],
        'context_inputs':[],
        'limitations':['Original marked roundabout lane topology requires Native operator survey',
                       'Requested slow speed, lane and pass phase do not establish impeding or necessity']}
    return {'format':'c132924-exact-native-request-v1','assignment_id':AID,
            'case_id':case_id,'selected_case_id':case_id,'supported_case_ids':[AID+'__'+s for s in SUFFIXES],
            'cell_id':'C132924','law_id':'NRS-484B-627-1b','actor':'motor_vehicle_driver',
            'frames':600,'rate_hz':20,'duration_s':30,'camera_sources':list(NAMES),
            'cameras':[{'name':name,'width':size[0],'height':size[1],
                        'fov_deg':fov,'pose_strategy':('fixed surveyed elevated roundabout' if name=='overview' else
                            'fixed surveyed lane boundary' if name=='reference_corner' else 'ego-mounted source')}
                       for name,size,fov in zip(NAMES,SIZES,FOV)],
            'required_atoms':[],'source_packets':[],
            'source_scope':'original Native lane/body/follower/pass source pending',
            'status':'authored_cpu_request_original_native_pending',
            'passing_exception_case':suffix in ('necessary_pass','post_pass_linger'),
            'case':{'case_id':case_id,'recording_description':description},
            'recording_description':description}


def main():
    SCRATCH.mkdir(parents=True,exist_ok=True)
    config = build('probe_a')
    for path in (ROOT/'native'/'config.json',ROOT/'config.json'):
        stage = SCRATCH/(path.name+'-'+path.parent.name+'.stage')
        stage.write_text(json.dumps(config,indent=2)+'\n')
        os.replace(stage,path)
    print(json.dumps({'selected_case_id':config['case_id'],'supported_cases':len(config['supported_case_ids'])}))


if __name__ == '__main__':
    main()
