"""Bind exact service/repair, numeric-boundary and exception comparisons."""
import json
from pathlib import Path
from build_constructions import description
from service_parking import CASES
from source_packet import ASSIGNMENT

ROOT=Path(__file__).resolve().parent
SOURCE='inputs/'+ASSIGNMENT+'/assignment.json'
SOURCE_SHA='46c20aa082043b0a81ae2bd6a741741f43429e7bda695e93b129fb8efb9bfb1b'


def write():
    path=ROOT/'case-plan.json'; plan=json.loads(path.read_text())
    ids={c.name:ASSIGNMENT+'__'+c.name for c in CASES}
    gap={'id':'no-accepted-heavy-service-parking-evidence',
         'requirement':'Commercial heavy vehicle parking near qualifying public school, service or repair activity, size and posted/loading branches',
         'source':{'path':SOURCE,'sha256':SOURCE_SHA},
         'why_existing_insufficient':'Frozen accepted recording inventory is empty.'}
    plan['evidence_review']['gaps']=[gap]
    plan['source_observation_mapping']={}
    plan['selected_branch']='Commercial vehicle used in conjunction with service or repair'
    plan['requirement_dispositions']=[{'requirement':'LVMC-11-52-305-A: commercial vehicle parking and its location, size, sign, loading and service-use alternatives',
        'source':{'path':SOURCE,'sha256':SOURCE_SHA},'status':'selected_required',
        'evidence_or_gap':'No accepted exact evidence; all alternatives and numeric boundaries are source-gated selected cases.',
        'case_ids':list(ids.values())}]
    plan['cases']=[{'case_id':ids[c.name], 'target_law_id':'LVMC-11-52-305-A',
        'kind':'delivery','new_capture_selected':True,'gap_ids':[gap['id']],
        'case_parameters':{k:getattr(c,k) for k in ('work_kind','work_near','length_ft','unladen_lb','adjacent_kind','frontage_ft','posted_permission','loading')},
        'recording_description':'Original 900-frame heavy vehicle parking, actual service work, independent length and unladen-weight sources, public adjacency/frontage, exact sign and four cameras.',
        'saved_measurement':'analysis.py measure_service_parking from original-service-parking.jsonl and service-parking-context.json',
        'physical_acceptance_claimed':False} for c in CASES]
    specs=(
      ('service_work_activity','service_school_24ft_8001lb','no_service',['work_kind']),
      ('repair_work_activity','service_school_24ft_8001lb','repair_near',['work_kind']),
      ('construction_work_activity','service_school_24ft_8001lb','construction_near',['work_kind']),
      ('similar_essential_work','service_school_24ft_8001lb','similar_essential_near',['work_kind']),
      ('worksite_proximity','service_school_24ft_8001lb','service_far',['work_near']),
      ('posted_permission','service_school_24ft_8001lb','posted_permission',['posted_permission']),
      ('expeditious_loading','no_service','expeditious_loading',['loading']),
      ('length_below_at','length_23_9ft','length_24_0ft',['length_ft']),
      ('length_at_above','length_24_0ft','length_24_1ft',['length_ft']),
      ('weight_below_at','weight_7999lb','weight_8000lb',['unladen_lb']),
      ('weight_at_above','weight_8000lb','weight_8001lb',['unladen_lb']),
      ('frontage_below_at','residence_299ft','residence_300ft',['frontage_ft']),
      ('frontage_at_above','residence_300ft','residence_301ft',['frontage_ft']),
      ('public_school_or_park','service_school_24ft_8001lb','public_park',['adjacent_kind']),
    )
    plan['comparisons']=[{'comparison_id':name,'case_ids':[ids[a],ids[b]],
        'fixed_conditions':['same public street, commercial heavy vehicle, parked interval, governed curb, four-view camera plan, and all case parameters except named differences'],
        'deliberate_differences':diff,'status':'original_comparison_pending'} for name,a,b,diff in specs]
    plan['observations']=[{'name':row['name'],'mandatory':True,'method':row['method'],
        'source':'original 900-frame Native readback, reviewed source packet and four camera frames'}
        for row in description()['channels']]
    plan['camera_plan']={'profile':'overview1080-capability','duration_s':45,
       'composition':'synchronized_four_view_primary',
       'coverage':[{'view':v,'subject':subject,'interval':'all 45 seconds'} for v,subject in (
          ('overview','qualifying street, heavy vehicle and worksite'),
          ('approach','heavy vehicle route and complete parked interval'),
          ('reference_corner','exact device face, curb and adjacent property'),
          ('driver_reference','driver, worker and actual service task'))]}
    plan['planning_status']='selected_heavy_service_parking_delivery_cpu_proofs_in_progress'
    plan['runtime_uncertainties']=['Actual Native parking and worksite activity, original pixels and source authority require local review.',
      'Immediate neighborhood, similar essential use, storage and modifier scope are unresolved legal judgments; engineering probe positions do not set legal cutoffs.']
    path.write_text(json.dumps(plan,indent=2)+'\n')


if __name__=='__main__':write()
