"""Independent fixed-grid source and construction isolation audit."""
from __future__ import annotations
import argparse,json,math
from pathlib import Path

def audit(manifest,grid,attempts):
    manifest=Path(manifest);folder=manifest.parent;m=json.loads(manifest.read_text());proposal=json.loads((folder/'proposals/cases.json').read_text())
    spec=next((s for s in proposal['sweep_specs'] if s['sweep_id']==grid),None)
    if spec is None or spec['status']!='complete':raise ValueError('Unknown or incomplete exact grid')
    ids=spec['selection_order']
    if len(ids)!=3 or len(attempts)!=3:raise ValueError('Exact three-point source set required')
    axis=spec['axes'][0];expected=[];measured=[];fixed=[];controls=[]
    for cid,path in zip(ids,map(Path,attempts)):
        entry=next(e for e in m['cases'] if e['case_id']==cid);case=next(c for c in proposal['cases'] if c['case_id']==cid)
        construction=json.loads((folder/entry['construction']).read_text());runner=next(f['content'] for f in construction['files'] if f['path']=='runner.py')
        report=json.loads((path/'analysis-report.json').read_text())
        if report['case_id']!=cid or report.get('physical_acceptance_claimed') or report.get('legal_acceptance_claimed'):
            raise ValueError('Wrong case source or unsupported acceptance')
        history=[json.loads(line) for line in (path/'backing_history.jsonl').read_text().splitlines()]
        trace=[json.loads(line) for line in (path/'trace.jsonl').read_text().splitlines()]
        frames=[json.loads(line) for line in (path/'video_frames.jsonl').read_text().splitlines()]
        if len(history)<3 or len(history)!=len(trace) or len(trace)!=len(frames):raise ValueError('Original source join incomplete')
        for h,t,f in zip(history,trace,frames):
            if h['frame']!=t['frame'] or h['frame']!=f['carla_frame'] or h['ego']['position_m']!=t['position_m']:
                raise ValueError('Original source join changed')
        key=axis['variable'];request=case['sweep_point'][key]
        if key=='other_traffic_spacing':
            value=math.dist(history[0]['ego']['position_m'],history[0]['other']['position_m'])
            token=f'waypoint.previous({request:.1f})'
        else:
            value=next((i for i in range(1,len(history)) if history[i]['other']['speed_mps']<history[i-1]['other']['speed_mps']-.05),None)
            token=f'len(frames)<{int(request)}'
        if token not in runner:raise ValueError('Frozen grid runner lacks requested control')
        context=json.loads((path/'sweep_context.json').read_text())
        if context.get(key)!=value:raise ValueError('Sweep context differs from original source')
        expected.append(request);measured.append(value);controls.append(token)
        fixed.append(([(h['frame'],h['time_s'],h['ego']['position_m']) for h in history],[(h['road_id'],h['lane_width_m']) for h in history]))
    if len(set(controls))!=3 or any(item!=fixed[0] for item in fixed[1:]):raise ValueError('Grid failed fixed ego/road isolation')
    return {'format':'worker-sweep-comparison-audit','grid':grid,'passed_protocol':True,'requested':expected,'measured_fixture':measured,
            'fixture_setpoints_distinct':len(set(measured))==3 and all(abs(a-b)<=2 for a,b in zip(expected,measured)),
            'physical_realization_established':False,
            'scope':'Synthetic original-shaped sources; real Native realization and legal judgment remain pending'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--grid',required=True);p.add_argument('--attempt',action='append',required=True);a=p.parse_args();print(json.dumps(audit(a.manifest,a.grid,a.attempt),indent=2))
if __name__=='__main__':main()
