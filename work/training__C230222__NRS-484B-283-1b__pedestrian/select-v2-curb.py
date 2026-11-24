"""Materialize canonical inspection files and preserve exact curb case scope."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    construction = json.loads((HERE/'v2-primary/probe_1/construction.json').read_text())
    plan = json.loads((HERE/'case-plan.json').read_text())
    case_ids = [case['case_id'] for case in plan['cases']]
    for item in construction['files']:
        target = HERE/item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])
    construction['status'] = 'draft'
    construction['measurement_plan'] = {
        'entrypoint':'finalize.py','output':'curb_departure_conditional_margin',
        'sources':['curb-samples.jsonl','curb-context.json','road.xodr','video_frames.jsonl'],
        'method':'Join the original 600-frame pedestrian footprint, curb departure, vehicle approach and frame map; retain conditional stopping assumption range.',
        'limitation':'Assumed reaction/deceleration is not measured driver capability or a legal cutoff.'}
    construction['static_checks'] = [
        {'name':'exact_case_offline','status':'passed','evidence':'v2-primary/probe_1/proofs/primary-offline.log'},
        {'name':'missing_source_negative','status':'passed','evidence':'v2-primary/probe_1/proofs/negative-analysis.log'}]
    construction['termination_rules'] = {
        'frame_budget':600,'duration_s':30,
        'capture_end':'600 synchronized ticks or explicit Native failure; retain original status.',
        'cleanup':'Close encoders, restore world and release owned actors before saved processing.'}
    construction['mechanisms'] = {
        'construction_status':'draft_executable',
        'world':'Authored straight OpenDRIVE road and curb boundary',
        'controller':'Pedestrian departure request .5 or 3.5 s with common observed-movement driver response policy',
        'cameras':'Four synchronized original RGB FFV1 streams'}
    (HERE/'construction.json').write_text(json.dumps(construction,indent=2)+'\n')
    plan['camera_plan'] = {
        'profile':'overview1080-capability','duration_s':30,
        'composition':'synchronized_four_view_primary',
        'coverage':[
            {'view':'overview','subject':'curb, pedestrian and approaching vehicle','interval':'entire 30 s'},
            {'view':'approach','subject':'approaching vehicle and roadway entry','interval':'departure through conflict'},
            {'view':'reference_corner','subject':'pedestrian footprint and curb edge','interval':'entire 30 s'},
            {'view':'driver_reference','subject':'vehicle response and pedestrian path','interval':'departure through closure'}]}
    channels = {channel['name'] for channel in construction['recording_description']['channels']}
    plan['observations'] = [{'name':name,'mandatory':True,
                             'source':'original Native curb samples, frame map and derived saved channel'}
                            for name in sorted(channels)]
    term_channels = {'ru.subject':'kin.position','st.road_edge':'rel.occupies',
                     'st.sidewalk':'rel.occupies','st.safety_zone':'rel.occupies',
                     'kin.speed':'kin.speed','kin.accel_longitudinal':'kin.accel_longitudinal',
                     'rel.occupies':'rel.occupies',
                     'drv.time_to_conflict':'drv.time_to_conflict',
                     'drv.stopping_distance':'drv.stopping_distance'}
    plan['source_observation_mapping'] = {
        term:{'evidence':'Curb source measurement and original source pixel review remain separate; the channel is a CPU acquisition plan.',
              'channels':[channel],'source_refs':['curb-samples.jsonl','curb-context.json','video_frames.jsonl']}
        for term,channel in term_channels.items()}
    plan['requirement_dispositions']=plan['requirement_dispositions'][:1]
    disposition=plan['requirement_dispositions'][0]
    disposition['status']='selected_required'
    disposition['case_ids']=case_ids
    disposition['branch']='Leaving a curb into a vehicle path, conditional inability to yield, and introductory cross-reference applicability'
    disposition['evidence_or_gap']='Both cases acquire original pedestrian and vehicle source traces and a conditional stopping range. Exact cross-reference texts are bound in statutory-crossrefs.json; original context review must resolve applicability. Numeric assumptions do not define statutory impossibility or actual driver capability.'
    for case in plan['cases']:
        case['kind']='selected_delivery_preparation'
        case['recording_description']=construction['recording_description']
        case['requested_not_measured']=True
    plan['blockers']=['Original Native motion, source pixels, actual driver capability and cross-reference applicability require local physical review.']
    (HERE/'case-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print(json.dumps({'selected_cases':len(case_ids),'root_files':len(construction['files'])}))


if __name__=='__main__':
    main()
