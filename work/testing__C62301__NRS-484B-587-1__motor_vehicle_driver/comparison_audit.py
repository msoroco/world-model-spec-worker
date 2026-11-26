"""Independent protocol for official access designation and route comparisons."""
import argparse
import json
from pathlib import Path
class ComparisonError(ValueError):pass
FIXED_FIELDS=('map_sha256','authority_determination_sha256','public_highway_boundary_sha256','official_device_inventory_sha256','ego_blueprint','driver_actor_id','camera_plan_sha256','duration_frames')
def audit(records,*,deliberate_differences):
 if len(records)<2 or not deliberate_differences:raise ComparisonError('separate records and deliberate differences required')
 for r in records:
  if r.get('format')!='controlled-access-delivery-measurement' or not r.get('case_id') or not r.get('native_result_sha256'):raise ComparisonError('missing sealed Native measurement')
  if r.get('frame_count')!=900 or r.get('full_video_decode') is not True or not r.get('actual_pixels') or not r.get('physical_completion'):raise ComparisonError('incomplete physical or pixel evidence')
  for f in FIXED_FIELDS:
   if r.get(f) in (None,''):raise ComparisonError('missing fixed condition: '+f)
 if len({r['case_id'] for r in records})!=len(records) or len({r['native_result_sha256'] for r in records})!=len(records):raise ComparisonError('separate Native captures required')
 first=records[0]
 for r in records[1:]:
  for f in FIXED_FIELDS:
   if r[f]!=first[f]:raise ComparisonError('fixed condition changed: '+f)
 for f in deliberate_differences:
  values=[r.get('observables',{}).get(f) for r in records]
  if None in values or len({json.dumps(v,sort_keys=True) for v in values})<2:raise ComparisonError('deliberate difference absent: '+f)
 return {'format':'controlled-access-comparison-audit','case_ids':[r['case_id'] for r in records],'fixed_conditions_checked':list(FIXED_FIELDS),'deliberate_differences':deliberate_differences,'status':'measurement_comparable_legal_judgment_unresolved'}
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--comparison',required=True);parser.add_argument('--records',type=Path,required=True);args=parser.parse_args();here=Path(__file__).resolve().parent
 plan=json.loads((here/'case-plan.json').read_text());found=[x for x in plan['comparisons'] if x['comparison_id']==args.comparison]
 if len(found)!=1:raise ComparisonError('unknown comparison')
 records=json.loads(args.records.read_text());ids=found[0]['case_ids']
 if set(records)!=set(ids):raise ComparisonError('comparison identities changed')
 result=audit([records[x] for x in ids],deliberate_differences=found[0]['deliberate_differences']);result['comparison_id']=args.comparison;print(json.dumps(result,indent=2))
if __name__=='__main__':main()
