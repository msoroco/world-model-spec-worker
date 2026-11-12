"""Independent source audit for the 80-inch subject/lead width controls."""
import argparse
import hashlib
import json
import math
from pathlib import Path

CASES=('gap_at_500ft','ego_width_below_80in','ego_width_at_80in','lead_width_below_80in')
THRESHOLD=80*.0254


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def inspect(root,suffix):
    root=Path(root);config=json.loads((root/'config.json').read_text())
    report=json.loads((root/'analysis-report.json').read_text())
    result=json.loads((root/'result.json').read_text())
    context=json.loads((root/'road_context.json').read_text())
    history=rows(root/'truck_history.jsonl');frames=rows(root/'video_frames.jsonl')
    if not config['selected_case_id'].endswith('__'+suffix) or result['case_id']!=config['selected_case_id']:
        raise ValueError('Width comparison case identity differs')
    if not history or len(history)!=len(frames) or any(
            f['carla_frame']!=h['frame'] or f['time_s']!=h['time_s'] or f['video_frame']!=i
            for i,(h,f) in enumerate(zip(history,frames))):
        raise ValueError('Width comparison original frame join differs')
    if context['same_direction_lane_count']!=1:
        raise ValueError('Width comparison changed one-lane condition')
    tx,ty=context['lane_forward_xy'];length=math.hypot(tx,ty)
    if not length:raise ValueError('Width comparison has no sourced lane tangent')
    tx,ty=tx/length,ty/length
    gaps=[]
    for row in history:
        if any(row[role]['road_id']!=context['road_id'] or
               row[role]['lane_id']!=context['lane_id'] or
               row[role].get('is_truck_or_combination') is not True
               for role in ('ego','lead')):
            raise ValueError('Width comparison lost same-lane truck relation')
        def projection(role):
            return [x*tx+y*ty for x,y in row[role]['body_vertices_xy_m']]
        gaps.append(min(projection('lead'))-max(projection('ego')))
    widths={role:min(float(h[role]['overall_width_m']) for h in history)
            for role in ('ego','lead')}
    if not math.isclose(min(gaps),report['measurements']['minimum_sampled_body_gap_m']['value'],abs_tol=1e-6):
        raise ValueError('Width comparison gap differs from source')
    if widths!=report['measurements']['minimum_overall_width_m']['value']:
        raise ValueError('Width comparison widths differ from source')
    for name in ('truck_history.jsonl','road_context.json','video_frames.jsonl'):
        checksum=hashlib.sha256((root/name).read_bytes()).hexdigest()
        if report['measurements']['minimum_overall_width_m']['sources'][name]!=checksum:
            raise ValueError('Width source hash differs: '+name)
    return {'case_id':result['case_id'],'widths_m':widths,'gap_m':min(gaps),
            'lane_count':context['same_direction_lane_count'],'road_id':context['road_id'],
            'lane_id':context['lane_id'],'cameras':config['cameras'],
            'rate_hz':config['rate_hz'],'duration_s':config['duration_s'],
            'required_atoms':config['required_atoms'],
            'blueprints':{role:{h[role]['blueprint_id'] for h in history} for role in ('ego','lead')}}


def audit(paths):
    if set(paths)!=set(CASES):raise ValueError('Supply exact 80-inch control cases')
    facts={suffix:inspect(paths[suffix],suffix) for suffix in CASES}
    base,ego_below,ego_at,lead_below=(facts[s] for s in CASES)
    for field in ('lane_count','road_id','lane_id','cameras','rate_hz','duration_s','required_atoms'):
        if len({json.dumps(facts[s][field],sort_keys=True) for s in CASES})!=1:
            raise ValueError('Width comparison changed fixed condition: '+field)
    if any(abs(facts[s]['gap_m']-152.4)>.05 for s in CASES):
        raise ValueError('Width comparison changed fixed body gap')
    if not (base['widths_m']['ego']>=THRESHOLD and base['widths_m']['lead']>=THRESHOLD and
            ego_below['widths_m']['ego']<THRESHOLD and
            math.isclose(ego_at['widths_m']['ego'],THRESHOLD,abs_tol=.005) and
            lead_below['widths_m']['lead']<THRESHOLD):
        raise ValueError('80-inch source boundary classification failed')
    if not (base['widths_m']['lead']==ego_below['widths_m']['lead']==ego_at['widths_m']['lead'] and
            base['widths_m']['ego']==lead_below['widths_m']['ego']):
        raise ValueError('Width comparison changed fixed counterpart width')
    if not (base['blueprints']['lead']==ego_below['blueprints']['lead']==ego_at['blueprints']['lead'] and
            base['blueprints']['ego']==lead_below['blueprints']['ego']):
        raise ValueError('Width comparison changed fixed counterpart truck')
    return {'format':'worker-width-boundary-comparison-audit','passed':True,
            'comparison_id':'qualifying_vehicle_width',
            'case_ids':[facts[s]['case_id'] for s in CASES],
            'measured_widths_m':{s:facts[s]['widths_m'] for s in CASES},
            'fixed_gap_m':152.4,
            'scope':'synthetic saved-source software audit; legal/physical status unresolved'}


def main():
    parser=argparse.ArgumentParser()
    for suffix in CASES:parser.add_argument('--'+suffix.replace('_','-'),required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args();output=Path(args.output)
    if output.exists():raise ValueError('Retain previous width comparison receipt')
    output.write_text(json.dumps(audit({s:getattr(args,s) for s in CASES}),indent=2)+'\n')


if __name__=='__main__':main()
