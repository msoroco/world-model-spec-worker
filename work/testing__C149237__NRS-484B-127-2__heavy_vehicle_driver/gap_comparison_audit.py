"""Independent saved-source audit for the three 500-foot engineering probes.

This checks controlled diagnostic differences; it makes no legal or physical
acceptance claim. It does not call the package finalizer or trust its channel
values without recomputing the original body projections.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

GAPS = {'gap_below_500ft':150.0, 'gap_at_500ft':152.4,
        'gap_above_500ft':155.0}


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def source_gap(row, tangent):
    tx,ty=tangent
    length=math.hypot(tx,ty)
    if length<=0:raise ValueError('Missing lane tangent')
    tx,ty=tx/length,ty/length
    projected={}
    for role in ('ego','lead'):
        actor=row[role]
        vertices=actor['body_vertices_xy_m']
        if len(vertices)<4 or not actor.get('is_truck_or_combination'):
            raise ValueError('Missing qualifying source body: '+role)
        projected[role]=[float(x)*tx+float(y)*ty for x,y in vertices]
    return min(projected['lead'])-max(projected['ego'])


def inspect(root, suffix):
    root=Path(root)
    config=json.loads((root/'config.json').read_text())
    result=json.loads((root/'result.json').read_text())
    report=json.loads((root/'analysis-report.json').read_text())
    context=json.loads((root/'road_context.json').read_text())
    history=rows(root/'truck_history.jsonl')
    mapping=rows(root/'video_frames.jsonl')
    if config['selected_case_id']!=result['case_id'] or not result['case_id'].endswith('__'+suffix):
        raise ValueError('Comparison case identity differs')
    if len(history)!=len(mapping) or not history:raise ValueError('Missing full frame join')
    if any(m['carla_frame']!=h['frame'] or m['time_s']!=h['time_s'] or m['video_frame']!=i
           for i,(h,m) in enumerate(zip(history,mapping))):
        raise ValueError('Original frame join differs')
    if context['same_direction_lane_count']!=1:
        raise ValueError('Gap comparison changed one-lane condition')
    widths={role:min(float(h[role]['overall_width_m']) for h in history)
            for role in ('ego','lead')}
    identities={role:{h[role]['blueprint_id'] for h in history} for role in ('ego','lead')}
    if any(len(values)!=1 for values in identities.values()):
        raise ValueError('Truck identity changed within case')
    gaps=[source_gap(h,context['lane_forward_xy']) for h in history]
    minimum=min(gaps)
    if not math.isclose(minimum,report['measurements']['minimum_sampled_body_gap_m']['value'],abs_tol=1e-6):
        raise ValueError('Finalizer gap differs from original body source')
    if not math.isclose(minimum,result['target_checks'][0]['measured'],abs_tol=1e-6):
        raise ValueError('Reported target check differs from original body source')
    if not math.isclose(result['target_checks'][0]['requested'],GAPS[suffix],abs_tol=1e-9):
        raise ValueError('Wrong engineering target')
    if abs(minimum-GAPS[suffix])>2:
        raise ValueError('Realized gap missed engineering target')
    for name in ('truck_history.jsonl','road_context.json','video_frames.jsonl'):
        checksum=hashlib.sha256((root/name).read_bytes()).hexdigest()
        if report['measurements']['minimum_sampled_body_gap_m']['sources'][name]!=checksum:
            raise ValueError('Measurement source hash differs: '+name)
    return {'case_id':result['case_id'],'minimum_gap_m':minimum,'widths_m':widths,
            'blueprints':{role:next(iter(values)) for role,values in identities.items()},
            'road_id':context['road_id'],'lane_id':context['lane_id'],
            'lane_count':context['same_direction_lane_count'],
            'rate_hz':config['rate_hz'],'duration_s':config['duration_s'],
            'cameras':config['cameras'],'required_atoms':config['required_atoms'],
            'source_hashes':report['measurements']['minimum_sampled_body_gap_m']['sources']}


def audit(paths):
    if set(paths)!=set(GAPS):raise ValueError('Supply exactly three gap cases')
    details={suffix:inspect(paths[suffix],suffix) for suffix in GAPS}
    fixed=('widths_m','blueprints','road_id','lane_id','lane_count',
           'rate_hz','duration_s','cameras','required_atoms')
    for field in fixed:
        values=[details[suffix][field] for suffix in GAPS]
        if values[1:]!=values[:-1]:raise ValueError('Fixed comparison condition differs: '+field)
    numbers=[details[suffix]['minimum_gap_m'] for suffix in GAPS]
    if not numbers[0]<numbers[1]<numbers[2]:
        raise ValueError('Below/at/above gap ordering failed')
    return {'format':'worker-gap-boundary-comparison-audit','passed':True,
            'comparison_id':'gap_500ft_boundary','case_ids':[details[s]['case_id'] for s in GAPS],
            'measured_gaps_m':numbers,'fixed_conditions':list(fixed),
            'scope':'synthetic saved-source software audit; legal and physical status unresolved'}


def main():
    parser=argparse.ArgumentParser()
    for suffix in GAPS:parser.add_argument('--'+suffix.replace('_','-'),required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    paths={suffix:getattr(args,suffix) for suffix in GAPS}
    output=Path(args.output)
    if output.exists():raise ValueError('Retain prior comparison receipt')
    output.write_text(json.dumps(audit(paths),indent=2)+'\n')


if __name__=='__main__':main()
