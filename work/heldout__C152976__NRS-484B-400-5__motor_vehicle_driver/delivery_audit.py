"""Independent original-source audit for C152976, without legal acceptance."""
import argparse
from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('site.json', 'video_frames.jsonl', 'native/footprints.jsonl',
           'native/road_edges.jsonl', 'trace.jsonl')


def _hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _signed_turn_gap(point, polyline):
    near = []
    for a, b in zip(polyline, polyline[1:]):
        dx, dy = b[0]-a[0], b[1]-a[1]
        length = dx*dx+dy*dy
        if length <= 1e-12: raise ValueError('Degenerate audited turn curb')
        t = max(0., min(1., ((point[0]-a[0])*dx+(point[1]-a[1])*dy)/length))
        x, y = a[0]+t*dx, a[1]+t*dy
        dist = hypot(point[0]-x, point[1]-y)
        cross = dx*(point[1]-y)-dy*(point[0]-x)
        near.append((dist, dist if cross<=0 else -dist))
    return min(near)[1]


def audit_attempt(attempt, analysis, case, *, decoder=None, receipt_dir=None):
    root = Path(attempt)
    report = json.loads(Path(analysis).read_text()) if not isinstance(analysis, dict) else analysis
    if report.get('case_id') != case:
        raise ValueError('Audited analysis selects another case')
    for name in (*SOURCES, 'config.json'):
        if not (root/name).is_file():
            raise ValueError('Missing audited original source: '+name)
    config = json.loads((root/'config.json').read_text())
    if config.get('selected_case_id') != case:
        raise ValueError('Audited Native config selects another case')
    source_hashes = report['measurements']['one_way_curb_history'].get('sources', {})
    expected = {'site.json','video_frames.jsonl','native/footprints.jsonl','native/road_edges.jsonl'}
    if set(source_hashes) != expected or any(_hash(root/name) != source_hashes[name] for name in expected):
        raise ValueError('Audited analysis source inventory differs')
    site = json.loads((root/'site.json').read_text())
    if not site.get('curb_source') or not site.get('one_way_source'):
        raise ValueError('Audited site lacks source identity')
    frames = _rows(root/'video_frames.jsonl')
    bodies = _rows(root/'native/footprints.jsonl')
    edges = _rows(root/'native/road_edges.jsonl')
    trace = _rows(root/'trace.jsonl')
    if not frames or len({len(frames),len(bodies),len(edges),len(trace)}) != 1:
        raise ValueError('Audited original source frame count differs')
    samples = report['measurements']['one_way_curb_history']['value']['samples']
    if len(samples) != len(frames):
        raise ValueError('Audited measured curb history incomplete')
    sections = set(); actor_id = None; minimum = {}
    for i,(frame,body,edge,motion,sample) in enumerate(zip(frames,bodies,edges,trace,samples)):
        ident = (frame.get('video_frame'),frame.get('carla_frame'),frame.get('time_s'))
        if ident[0] != i or frame.get('native_frame') != ident[1]:
            raise ValueError('Audited original frame map changed')
        if any((row.get('video_frame'),row.get('carla_frame'),row.get('time_s')) != ident
               for row in (body,edge)) or (motion.get('frame'),motion.get('time_s')) != ident[1:]:
            raise ValueError('Audited original time join differs')
        if actor_id is None: actor_id = body.get('actor_id')
        if actor_id != body.get('actor_id') or actor_id != frame.get('subject_actor_id'):
            raise ValueError('Audited subject actor identity changed')
        if edge.get('road_id') != body.get('road_id'):
            raise ValueError('Audited body/curb road identity differs')
        if (edge.get('site_file_sha256') != _hash(root/'site.json') or
                edge.get('one_way_source') != site['one_way_source'] or
                edge.get('curb_source') != site['curb_source'] or
                edge.get('turn_left_edge_polyline_xy') != site.get('turn_left_edge_polyline_xy')):
            raise ValueError('Audited site/curb binding differs')
        corners = body.get('body_corners_xy')
        if not isinstance(corners,list) or len(corners)<4 or any(
                not isinstance(p,list) or len(p)!=2 or any(type(v) not in (int,float) or not isfinite(v) for v in p)
                for p in corners):
            raise ValueError('Audited full-body corners missing')
        segment = edge.get('native_road_direction')
        if segment == 'north':
            gap = min(p[0] for p in corners)-edge['observed_left_curb_x']; label='approach'
        elif segment == 'west':
            gap = min(p[1] for p in corners)-edge['observed_left_curb_y']; label='departure'
        elif segment == 'turn':
            gap = min(_signed_turn_gap(p,site['turn_left_edge_polyline_xy']) for p in corners);label='turn'
        else: raise ValueError('Audited one-way route segment missing')
        if sample.get('segment') != label or abs(sample.get('left_body_to_curb_gap_m',float('inf'))-gap)>1e-6:
            raise ValueError('Audited curb measurement differs from original bodies')
        sections.add(label);minimum[label]=min(gap,minimum.get(label,gap))
    if sections != {'approach','turn','departure'}:
        raise ValueError('Audited approach/turn/departure coverage incomplete')
    value = report['measurements']['one_way_curb_history']['value']
    for label,key in [('approach','minimum_approach_gap_m'),('turn','minimum_turn_gap_m'),('departure','minimum_departure_gap_m')]:
        if abs(minimum[label]-value[key])>1e-6:
            raise ValueError('Audited segment minimum differs')
    if decoder is None:
        from worker_exchange.media import audit as decoder
    if receipt_dir is not None: Path(receipt_dir).mkdir(parents=True,exist_ok=False)
    cameras={}
    for name in CAMERAS:
        path=root/(name+'.mkv')
        if not path.is_file():raise ValueError('Missing audited original camera: '+name)
        receipt=None if receipt_dir is None else Path(receipt_dir)/(name+'-decode.json')
        decoded=decoder(path,len(frames),mapping_sha256=_hash(root/'video_frames.jsonl'),receipt=receipt)
        if decoded.get('frames')!=len(frames):raise ValueError('Audited full camera decode incomplete')
        cameras[name]={'source_sha256':_hash(path),'decode':decoded}
    return {'format':'worker-one-way-source-audit','case_id':case,'frame_count':len(frames),
            'source_hashes':source_hashes,'camera_decodes':cameras,
            'segment_minima_m':minimum,
            'checks':{'native_source':True,'all_participants':True,'time_join':True,
                      'full_video_decode':True,'actual_pixels':'source_frames_decoded_only',
                      'physical_completion':'unverified'},
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True)
    parser.add_argument('--attempt',required=True);parser.add_argument('--analysis',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    output=Path(args.output)
    if output.exists():raise ValueError('Retain previous source-audit receipt')
    result=audit_attempt(args.attempt,args.analysis,args.case,
                         receipt_dir=output.parent/(output.stem+'-decodes'))
    output.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
