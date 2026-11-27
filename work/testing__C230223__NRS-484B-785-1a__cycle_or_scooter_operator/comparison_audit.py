"""Independent exact-case source joins and controlled scooter comparisons."""
import argparse
import hashlib
import json
from pathlib import Path
from package_spec import AID
from scooter_785 import need


HERE=Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_case(case_id,folder):
    folder=Path(folder).resolve()
    report_path=folder/'analysis-report.json'
    need(report_path.is_file() and not report_path.is_symlink(),
         'Missing comparison analysis report: '+case_id)
    report=json.loads(report_path.read_text())
    need(report.get('case_id')==case_id and report.get('analysis_complete') is True,
         'comparison report identity or analysis incomplete')
    data=report.get('measurements',{})
    keys={'scooter_qualification','bicycle_lane_occupancy',
          'speed_history_mph','ordinance_context'}
    need(set(data)>=keys,'Missing comparison measurement')
    for key in keys:
        item=data[key]
        need(item.get('method')=='source_sealed_scooter_measurement' and
             isinstance(item.get('sources'),dict) and
             set(item['sources'])=={'scooter-history.json','original-source-receipt.json',
                                    'trace.jsonl','video_frames.jsonl'},
             'comparison source binding missing: '+key)
        for name,digest in item['sources'].items():
            path=folder/name
            need(path.is_file() and not path.is_symlink() and sha(path)==digest,
                 'comparison source changed: '+name)
    return {key:data[key]['value'] for key in keys}


def audit(comparison_id,source_index,diagnostic_fault=None):
    plan=json.loads((HERE/'case-plan.json').read_text())
    comparison=next((item for item in plan['comparisons']
                     if item['comparison_id']==comparison_id),None)
    need(comparison is not None,'unknown exact scooter comparison')
    index=json.loads(Path(source_index).read_text())
    need(index.get('format')=='scooter-785-comparison-sources' and
         set(index.get('cases',{}))==set(comparison['case_ids']),
         'comparison source index does not cover exact cases')
    values={cid:load_case(cid,index['cases'][cid])
            for cid in comparison['case_ids']}
    ordered=[values[cid] for cid in comparison['case_ids']]
    if diagnostic_fault=='fixed':
        ordered[-1]=json.loads(json.dumps(ordered[-1]))
        if comparison_id=='scooter_qualification':
            ordered[-1]['ordinance_context']['kind']='reviewed_ordinance'
        else:
            ordered[-1]['scooter_qualification']['qualifies']=not ordered[0]['scooter_qualification']['qualifies']
    def same(key,field):
        need(all(row[key][field]==ordered[0][key][field] for row in ordered[1:]),
             'Fixed condition changed: '+key+'.'+field)
    if comparison_id=='speed_below_at_above':
        for key,field in [('scooter_qualification','qualifies'),
                          ('bicycle_lane_occupancy','designated_lane_id'),
                          ('ordinance_context','kind')]:
            same(key,field)
        requests=[row['speed_history_mph']['requested_mph'] for row in ordered]
        measured=[row['speed_history_mph']['steady_mean_mph'] for row in ordered]
        need(requests==[14.5,15,15.5] and measured[0]<measured[1]<measured[2],
             'measured 15 mph boundary comparison missing or unordered')
    elif comparison_id=='ordinance_context':
        same('scooter_qualification','qualifies')
        same('bicycle_lane_occupancy','designated_lane_id')
        same('speed_history_mph','requested_mph')
        need([row['ordinance_context']['kind'] for row in ordered]==['none','reviewed_ordinance'],
             'official ordinance context difference missing')
    elif comparison_id=='scooter_qualification':
        same('ordinance_context','kind')
        same('bicycle_lane_occupancy','designated_lane_id')
        same('speed_history_mph','requested_mph')
        need([row['scooter_qualification']['qualifies'] for row in ordered]==[True,False],
             'scooter definition difference missing')
    else:
        same('scooter_qualification','qualifies')
        same('ordinance_context','kind')
        same('speed_history_mph','requested_mph')
        scenes=[json.loads((Path(index['cases'][cid])/'scooter-history.json').read_text())['scene']
                for cid in comparison['case_ids']]
        need(scenes[0]['ego_route_xy']==scenes[1]['ego_route_xy'] and
             scenes[0]['roadway_rect_m']==scenes[1]['roadway_rect_m'] and
             scenes[0]['bicycle_lane_rect_m']!=scenes[1]['bicycle_lane_rect_m'],
             'Fixed route/roadway or deliberate designated-lane geometry differs')
        occupied=[row['bicycle_lane_occupancy']['occupied_frames'] for row in ordered]
        need(occupied[0]>0 and occupied[1]==0,
             'original body bicycle-lane occupancy difference missing')
    return {'format':'scooter-785-independent-comparison-audit',
            'assignment_id':AID,'comparison_id':comparison_id,
            'case_ids':comparison['case_ids'],'passed':True,
            'fixed_conditions_checked':comparison['fixed_conditions'],
            'deliberate_differences_checked':comparison['deliberate_differences'],
            'legal_verdict_claimed':False,'original_physical_acceptance_claimed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--comparison-id',required=True)
    parser.add_argument('--source-index',type=Path,required=True)
    parser.add_argument('--diagnostic-fault',choices=['fixed'])
    args=parser.parse_args()
    print(json.dumps(audit(args.comparison_id,args.source_index,args.diagnostic_fault),indent=2))
