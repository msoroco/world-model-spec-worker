"""Build distinct, source-joined CPU diagnostics for subsection 2 exclusions.

These are construction fixtures. They do not establish that an authored device
is official, or that original CARLA actors follow the requested paths.
"""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
REPO = BASE.parents[1]
SOURCE = BASE / 'selected-v3/controlled_2/primary/sources'
CASES = ('device_controlled', 'opposing_no_turn', 'opposing_left_turn')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def body(x, y, yaw):
    out = []
    for dx in (-2.0, 2.0):
        for dy in (-0.9, 0.9):
            for z in (-0.7, 0.7):
                out.append([round(x + dx*math.cos(yaw) - dy*math.sin(yaw), 6),
                            round(y + dx*math.sin(yaw) + dy*math.cos(yaw), 6), z])
    return out


def other_pose(t, turn):
    # Opposing approach follows highway A's reverse direction. A left-turn
    # request diverges only after the junction entry; the paired control does
    # not turn. Original motion remains a later Native measurement.
    if not turn or t <= 6:
        return max(-50.0, 50.0 - 5*t), 1.75, math.pi
    arc_time = math.pi*20/10
    if t <= 6 + arc_time:
        theta = (t-6)*5/20
        return round(20 - 20*math.sin(theta), 6), \
            round(-18.25 + 20*math.cos(theta), 6), math.pi + theta
    return 0.0, round(-18.25 - 5*(t-6-arc_time), 6), 3*math.pi/2


def build(suffix):
    assert suffix in CASES
    out = HERE / suffix / 'sources'
    out.mkdir(parents=True, exist_ok=True)
    baseline = json.loads((SOURCE / 'actor-history.json').read_text())
    opposing = suffix.startswith('opposing_')
    turn = suffix == 'opposing_left_turn'
    device = suffix == 'device_controlled'
    baseline['case_id'] = BASE.name + '__' + suffix
    baseline['format'] = 'c111294-2502-branch-diagnostic-v1'
    baseline['branch_context'] = suffix
    baseline['original_native_observed'] = False
    baseline['legal_verdict'] = None
    for row in baseline['rows']:
        row['authored_official_device_count'] = 1 if device else 0
        row['opposing_approaches'] = opposing
        row['other_left_turn_intent'] = turn
        if opposing:
            x,y,yaw = other_pose(row['time_s'], turn)
            other = row['other']
            other['center_xyz_m'] = [x,y,0]
            other['body_xyz_m'] = body(x,y,yaw)
            other['yaw_rad'] = round(yaw, 9)
            other['speed_mps'] = 5
    put(out/'actor-history.json', baseline)
    road = (SOURCE/'road.xodr').read_text()
    if device:
        signal = ('<signal id="25021" name="authored-control-request" s="35" t="-1.75" '
                  'dynamic="yes" orientation="+" zOffset="3" country="US" '
                  'type="1000001" subtype="0" value="0"/>')
        road = road.replace('<signals/></road>', '<signals>' + signal + '</signals></road>', 1)
    elif opposing:
        # The reverse direction uses a parallel authored approach of highway A.
        # It is a requested route, not a claim of generated OpenDRIVE acceptance.
        road = road.replace('name="uncontrolled crossed highways"',
                            'name="crossed highways with opposing A approach"')
    (out/'road.xodr').write_text(road)
    context = {'source_kind':'synthetic_cpu_diagnostic',
               'branch_context':suffix,
               'ego_highway_roads':[250,251,252],
               'other_highway_roads':[250,251,252] if opposing else [253,254,255],
               'authored_device_count':1 if device else 0,
               'official_device_governance_verified':False,
               'opposite_direction_left_turn_exclusion_resolved':False,
               'subsection_4_exception_resolved':False,
               'original_native_observed':False,
               'legal_verdict':None}
    put(out/'road-context.json', context)
    trace = [json.loads(line) for line in (SOURCE/'trace.jsonl').read_text().splitlines()]
    frame_map = [json.loads(line) for line in (SOURCE/'video_frames.jsonl').read_text().splitlines()]
    evidence = [json.loads(line) for line in (SOURCE/'capture/evidence.jsonl').read_text().splitlines()]
    if len(trace) != len(frame_map) or len(trace) != len(evidence) or len(trace) != 600:
        raise ValueError('Broken baseline source join')
    for row,ev in zip(baseline['rows'],evidence):
        other = row['other']
        ev['other_actors'][0]['body_vertices_m'] = other['body_xyz_m']
        ev['other_actors'][0]['position_m'] = other['center_xyz_m']
        ev['other_actors'][0]['heading_deg'] = round(math.degrees(other.get('yaw_rad', math.pi/2)), 6)
        ev['branch_context'] = suffix
        ev['authored_official_device_count'] = 1 if device else 0
        ev['opposing_approaches'] = opposing
        ev['other_left_turn_intent'] = turn
    jsonl(out/'trace.jsonl',trace)
    jsonl(out/'video_frames.jsonl',frame_map)
    jsonl(out/'capture/evidence.jsonl',evidence)
    put(out/'capture/manifest.json',{'extraction_confirmed':True,'frames':600,
                                    'synthetic_diagnostic':True,
                                    'branch_context':suffix,
                                    'sources':{'road.xodr':sha(out/'road.xodr'),
                                               'trace.jsonl':sha(out/'trace.jsonl')}})
    inventory = {str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
    put(HERE/suffix/'source-inventory.json',{
        'format':'c111294-2502-branch-source-inventory-v1',
        'case_id':baseline['case_id'], 'sources':inventory,
        'rows':600,'original_native_observed':False,'legal_verdict':None})
    original_spec = BASE/'selected-v3/controlled_2/primary/fixture-spec.json'
    spec = json.loads(original_spec.read_text())
    for frame,graph in enumerate(spec['graphs']):
        other=baseline['rows'][frame]['other']
        node=next(node for node in graph['nodes'] if node['id']=='other')
        node['attributes']['vertex']=other['center_xyz_m']
        node['attributes']['threedbbox']=other['body_xyz_m']
        yaw=other.get('yaw_rad', math.pi/2)
        node['attributes']['forward']=[round(math.cos(yaw),6),round(math.sin(yaw),6),0.0]
        graph['attributes']['branch_context']=suffix
    spec_path=HERE/suffix/'fixture-spec.json'
    put(spec_path,spec)
    if spec_path.stat().st_size>2*1024*1024:
        raise ValueError('Branch fixture generator exceeds returned-file limit')
    recipe={'format':'worker-fixture-recipe',
            'sources':[{'path':name,'source':str((out/name).relative_to(REPO)),
                        'sha256':digest} for name,digest in inventory.items()],
            'generator':{'source':str(spec_path.relative_to(REPO)),
                         'sha256':sha(spec_path)}}
    put(HERE/suffix/'fixture-recipe.json',recipe)
    return {'case_id':baseline['case_id'],'source_inventory_sha256':sha(HERE/suffix/'source-inventory.json')}


if __name__ == '__main__':
    print(json.dumps([build(suffix) for suffix in CASES]))
