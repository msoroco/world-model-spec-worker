"""Independent original-only safety-zone corridor, distance and exception contrasts."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from safety_zone import CASES, THIRTY_FT_M

AID='testing__C229455__NRS-484B-450-1h__motor_vehicle_driver'
PAIRS={
 'between_vs_outside':('between_park','outside_corridor_park','placement'),
 'west_below_vs_at':('west_end_below_30ft','west_end_at_30ft','offset_m'),
 'west_at_vs_above':('west_end_at_30ft','west_end_above_30ft','offset_m'),
 'west_vs_east_below':('west_end_below_30ft','east_end_below_30ft','end'),
 'park_vs_stop':('between_park','between_stop','activity'),
 'park_vs_stand':('between_park','between_stand','activity'),
 'ordinary_vs_conflict':('between_stop','between_stop_conflict','exception'),
 'ordinary_vs_law':('between_park','between_park_law','exception'),
 'ordinary_vs_officer':('between_stand','between_stand_officer','exception'),
 'ordinary_vs_device':('between_park','between_park_device','exception')}

def require(ok,message):
    if not ok:raise ValueError(message)

def audit_pair(comparison_id,reports):
    selection=PAIRS.get(comparison_id)
    require(selection is not None,'unknown safety-zone comparison')
    left_suffix,right_suffix,difference=selection
    ids=[AID+'__'+left_suffix,AID+'__'+right_suffix]
    pair=[reports.get(cid) for cid in ids]
    for cid,report in zip(ids,pair):
        require(isinstance(report,dict) and report.get('format')=='worker-delivery-audit' and
          report.get('passed') is True and report.get('protocol_fixture_checked') is False and
          report.get('case_id')==cid and report.get('frame_count')==900 and
          report.get('physical_acceptance_claimed') is True and
          report.get('comparison_record',{}).get('source_kind')=='original_native_capture',
          'original accepted report required: '+cid)
    a,b=[r['comparison_record'] for r in pair]
    for key in ('fixed_source_sha256','camera_plan','duration_s'):
        require(a.get(key) and a[key]==b.get(key),'changed fixed original condition: '+key)
    left,right=[next(c for c in CASES if c.case_id==name) for name in (left_suffix,right_suffix)]
    attrs=('placement','end','offset_m','activity','exception')
    for record,case in ((a,left),(b,right)):
        require(all(record.get(name)==getattr(case,name) for name in attrs),
                'original case variables differ')
        measured=record.get('measurement',{})
        require(measured.get('frame_count')==900 and
                type(measured.get('terminal_signed_end_station_m')) in (int,float) and
                type(measured.get('terminal_between_zone_and_curb')) is bool and
                measured.get('statutory_distance_reference_m')==THIRTY_FT_M,
                'original body, end station or statutory reference absent')
        if case.placement=='between':
            require(measured['terminal_between_zone_and_curb'] is True,
                    'between-zone-and-curb original body contrast absent')
        elif case.placement=='outside':
            require(measured['terminal_between_zone_and_curb'] is False,
                    'outside-corridor original body contrast absent')
        else:
            require(abs(measured['terminal_signed_end_station_m']-case.offset_m)<=.05,
                    'original end-station target not achieved')
    require(all(getattr(left,name)==getattr(right,name) for name in attrs if name!=difference),
            'undeclared case variable changed')
    require(getattr(left,difference)!=getattr(right,difference),
            'declared comparison variable did not change')
    x=a['measurement'];y=b['measurement']
    if difference=='offset_m':
        require(x['terminal_signed_end_station_m']<y['terminal_signed_end_station_m'],
                'original below/at/above distance order absent')
    if difference=='end':
        require(abs(x['terminal_signed_end_station_m']-y['terminal_signed_end_station_m'])<=.1,
                'both opposite-end probes did not hold distance fixed')
    return {'format':'c229455-independent-original-comparison-v1',
      'comparison_id':comparison_id,'case_ids':ids,
      'fixed_source_sha256':a['fixed_source_sha256'],
      'terminal_signed_end_stations_m':[x['terminal_signed_end_station_m'],
                                         y['terminal_signed_end_station_m']],
      'terminal_between_zone_and_curb':[x['terminal_between_zone_and_curb'],
                                         y['terminal_between_zone_and_curb']],
      'physical_comparison_passed':True,'legal_verdict_claimed':False}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report-map',type=Path,required=True)
    parser.add_argument('--comparison',choices=tuple(PAIRS),required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    paths=json.loads(args.report_map.read_text())
    reports={cid:json.loads(Path(path).read_text()) for cid,path in paths.items()}
    result=audit_pair(args.comparison,reports)
    if args.output.exists():raise ValueError('refusing to overwrite prior comparison audit')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
if __name__=='__main__':main()
