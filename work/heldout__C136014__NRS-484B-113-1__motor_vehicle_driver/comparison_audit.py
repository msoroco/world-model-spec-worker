"""Independent original-source comparison audit; no legal or physical acceptance."""
from __future__ import annotations
import argparse,json,math
from pathlib import Path

CASE_BASE='heldout__C136014__NRS-484B-113-1__motor_vehicle_driver__'

def rows(path):
    if not path.is_file():raise ValueError('Missing original source: '+path.name)
    data=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len(data)<3:raise ValueError('Insufficient original samples')
    return data

def read_case(folder,slug):
    folder=Path(folder);history=rows(folder/'backing_history.jsonl');trace=rows(folder/'trace.jsonl');frames=rows(folder/'video_frames.jsonl')
    if not (len(history)==len(trace)==len(frames)):raise ValueError('Original source time join differs')
    for h,t,f in zip(history,trace,frames):
        if h['frame']!=t['frame'] or h['frame']!=f['carla_frame'] or abs(h['time_s']-t['time_s'])>1e-5 or abs(h['time_s']-f['time_s'])>1e-5:
            raise ValueError('Original source time join differs')
        if h['ego']['position_m']!=t['position_m'] or h['ego_reverse_gear'] is not True:
            raise ValueError('Reverse ego original differs from trace')
        if h['lane_width_m']>3.0 or not h['road_id']:
            raise ValueError('Narrow road source condition changed')
    road={(h['road_id'],h['lane_width_m']) for h in history}
    if len(road)!=1:raise ValueError('Narrow road source condition changed')
    report=json.loads((folder/'analysis-report.json').read_text())
    if report['case_id']!=CASE_BASE+slug or report.get('physical_acceptance_claimed') or report.get('legal_acceptance_claimed'):
        raise ValueError('Wrong case or acceptance claim')
    recorded=report['measurements']['reverse_encounter']['value']
    gaps=[math.dist(h['ego']['position_m'],h['other']['position_m']) for h in history]
    min_gap=min(gaps);speed_change=history[-1]['other']['speed_mps']-history[0]['other']['speed_mps']
    reverse=math.dist(history[0]['ego']['position_m'],history[-1]['ego']['position_m'])
    if any(abs(a-b)>1e-5 for a,b in [(min_gap,recorded['min_center_distance_m']),(speed_change,recorded['other_speed_change_mps']),(reverse,recorded['reverse_displacement_m'])]):
        raise ValueError('Analysis report differs from original sources')
    for name in ('overview','approach','reference_corner','driver_reference'):
        if not (folder/(name+'.mkv')).is_file():raise ValueError('Missing original four-view video: '+name)
    return {'road':road.pop(),'ego':[(h['frame'],h['time_s'],h['ego']['position_m']) for h in history],
            'other_speeds':[h['other']['speed_mps'] for h in history],
            'gap':min_gap,'speed_change':speed_change,'reverse':reverse,'frames':len(history)}

def audit(comparison,primary,paired):
    base=read_case(primary,'reverse_clear_traffic_steady')
    slug={'traffic_clearance':'reverse_close_traffic_steady','traffic_interference':'reverse_clear_traffic_brakes'}.get(comparison)
    if slug is None:raise ValueError('Unknown comparison')
    other=read_case(paired,slug)
    if base['road']!=other['road'] or base['ego']!=other['ego'] or abs(base['reverse']-other['reverse'])>1e-5 or base['frames']!=other['frames']:
        raise ValueError('Fixed road or ego reverse trajectory changed')
    if comparison=='traffic_clearance':
        if base['other_speeds']!=other['other_speeds'] or not other['gap']<base['gap']-1:
            raise ValueError('Clearance comparison changed speed or lacks gap difference')
    else:
        if abs(base['gap']-other['gap'])>1e-5 or not other['speed_change']<base['speed_change']-0.2:
            raise ValueError('Interference comparison changed gap or lacks speed response')
    return {'format':'worker-comparison-audit','comparison_id':comparison,'passed':True,'source_frames':base['frames'],
            'primary_min_center_distance_m':base['gap'],'paired_min_center_distance_m':other['gap'],
            'primary_other_speed_change_mps':base['speed_change'],'paired_other_speed_change_mps':other['speed_change'],
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--comparison',required=True);p.add_argument('--primary',required=True);p.add_argument('--paired',required=True)
    a=p.parse_args();print(json.dumps(audit(a.comparison,a.primary,a.paired),indent=2))
if __name__=='__main__':main()
