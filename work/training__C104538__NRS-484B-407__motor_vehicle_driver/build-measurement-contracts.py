"""Draft source-bound Native measurement obligations; not pinned-valid receipts."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
PLAN=json.loads((HERE/'case-plan.json').read_text())


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,obj):path.write_text(json.dumps(obj,indent=2)+'\n')


def build():
    rows=[]
    procedures=(
      ('turn_and_two_direction_visibility',
       ['road_geometry.json','native_body_history.jsonl','driver_eye_rays.jsonl','video_frames.jsonl'],
       'Original complete reversal and target body visibility from approaching driver eyes on both directions within 500 ft'),
      ('crest_or_curve_at_turn',
       ['road.xodr','road_geometry.json','native_body_history.jsonl'],
       'Native loaded curve/crest and maneuver station, not authored road alone'),
      ('multi_movement_reversal_history',
       ['native_body_history.jsonl','trace.jsonl'],
       'Original heading, footprint and direction after reversal, including any backing movements'),
      ('sightline_boundary_and_pixels',
       ['driver_eye_rays.jsonl','video_frames.jsonl','reference_left.mkv','reference_right.mkv'],
       'Measured eye/body line of sight and audited original pixels at 500 ft from either direction'))
    for suffix in ('below_500_ft','at_500_ft','above_500_ft'):
        case_id=PLAN['assignment_id']+'__'+suffix
        source=HERE/'draft-sightline'/suffix
        obligations=[]
        for index,(key,inputs,method) in enumerate(procedures):
            disposition=PLAN['requirement_dispositions'][index]
            assert case_id in disposition['case_ids']
            obligations.append({'disposition_index':index,
                                'requirement':disposition['requirement'],
                                'source':disposition['source'],
                                'future_output_key':key,
                                'required_original_native_inputs':inputs,
                                'measurement_obligation':method,
                                'native_value_measured':False})
        contract={'format':'c104538-unselected-measurement-contract-draft-v1',
                  'case_id':case_id,'status':'requires_original_native_sources',
                  'authored_source_hashes':{name:sha(source/name)
                     for name in ('road.xodr','obstruction.json','measurement.json')},
                  'requirements':obligations,'pinned_contract_validated':False,
                  'saved_native_report_verified':False,
                  'legal_verdict_claimed':False}
        path=HERE/'draft-candidates'/suffix/'measurement-contract-draft.json'
        write(path,contract)
        rows.append({'case_id':case_id,'contract':str(path.relative_to(HERE)),
                     'sha256':sha(path),'native_measurements':0})
    result={'format':'c104538-measurement-contract-draft-summary-v1',
            'cases':rows,'count':3,'pinned_contracts_passed':0,
            'native_measurements':0}
    write(HERE/'draft-measurement-contract-summary.json',result)
    return result


if __name__=='__main__':print(json.dumps(build(),indent=2))
