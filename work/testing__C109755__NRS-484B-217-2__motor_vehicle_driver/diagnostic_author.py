"""Build a law-specific text diagnostic atop the pinned CPU graph/video example.

The example graph and color frames exercise adapters only. The authored stripe,
signal and participant histories are synthetic and never assert Native coverage.
"""
import hashlib
import json
from pathlib import Path
from traffic_sweep import select as select_traffic

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def main():
    spec = json.loads((REPO/'runtime/fixtures/example.json').read_text())
    files = spec['files']
    trace = [json.loads(line) for line in files['trace.jsonl'].splitlines() if line.strip()]
    scene=json.loads((ROOT/'scene.json').read_text())
    _,policy,_=select_traffic(scene,'baseline')
    files['traffic-policy.json']=json.dumps(policy,sort_keys=True)+'\n'
    zone = {'zone_kind':'marked_no_passing_zone','striping_source':'native_map',
            'stripe_y_m':0.0,'crossing_x_m':scene['crossing_x_m'],
            'zone_extent_verified':False,
            'statutory_exceptions_verified':False,
            'traffic_sweep_variant_id':'baseline',
            'traffic_policy_sha256':digest(files['traffic-policy.json']),
            'diagnostic_only':True}
    files['zone-context.json'] = json.dumps(zone,sort_keys=True)+'\n'
    rows = []
    for index, point in enumerate(trace):
        # Four synthetic samples start wholly below the stripe, then the
        # leading body edge crosses it. The body center is deliberately later.
        center_y = -2.0 + index * .5
        body = [[0,center_y-.5,0],[1,center_y-.5,0],
                [1,center_y+.5,0],[0,center_y+.5,0]]
        rows.append({'frame':point['frame'],'time_s':point['time_s'],
                     'ego_center_y_m':center_y,'ego_body_vertices_m':body,
                     'left_signal':index>=1,
                     'oncoming_body_gap_m':20.0,'following_body_gap_m':15.0,
                     'oncoming_velocity_xy_mps':[-2.0+0.1*index,0.0],
                     'following_velocity_xy_mps':[2.0-0.1*index,0.0],
                     'traffic_command_velocity_x_mps':{
                         'oncoming':-2.0,'following':2.0},
                     'oncoming_body_vertices_m':[[v[0]+21,v[1],v[2]] for v in body],
                     'following_body_vertices_m':[[v[0]-16,v[1],v[2]] for v in body]})
    files['turn-history.jsonl'] = ''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows)
    files['acquisition.json'] = json.dumps({name:{'kind':'original_native','sha256':digest(files[name])}
                                            for name in ('turn-history.jsonl','zone-context.json',
                                                         'traffic-policy.json')},sort_keys=True)+'\n'
    files['fixture-provenance.json'] = json.dumps({
        'scope':'CPU diagnostic only; reused adapter graphs and synthetic color frames',
        'case_specific_sources':['turn-history.jsonl','zone-context.json','traffic-policy.json'],
        'physical_acceptance_claimed':False},sort_keys=True)+'\n'
    output = ROOT/'diagnostic.json'
    output.write_text(json.dumps(spec,ensure_ascii=False,separators=(',',':'))+'\n')
    source = str(output.relative_to(REPO))
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    assignment=REPO/'inputs'/ROOT.name/'assignment.json'
    recipe = {'format':'worker-fixture-recipe','sources':[
                  {'path':'diagnostic-input.json','source':str(assignment.relative_to(REPO)),
                   'sha256':hashlib.sha256(assignment.read_bytes()).hexdigest()}],
              'generator':{'source':source,'sha256':checksum}}
    (ROOT/'diagnostic-recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
    unsignaled=json.loads(json.dumps(spec))
    negative_rows=[]
    for line in unsignaled['files']['turn-history.jsonl'].splitlines():
        row=json.loads(line)
        row['left_signal']=False
        negative_rows.append(row)
    unsignaled['files']['turn-history.jsonl']=''.join(json.dumps(row,sort_keys=True)+'\n' for row in negative_rows)
    unsignaled['files']['acquisition.json']=json.dumps({
        name:{'kind':'original_native','sha256':digest(unsignaled['files'][name])}
        for name in ('turn-history.jsonl','zone-context.json','traffic-policy.json')},sort_keys=True)+'\n'
    other=ROOT/'diagnostic-unsignaled.json'
    other.write_text(json.dumps(unsignaled,ensure_ascii=False,separators=(',',':'))+'\n')
    other_recipe=dict(recipe,generator={'source':str(other.relative_to(REPO)),
                                        'sha256':hashlib.sha256(other.read_bytes()).hexdigest()})
    (ROOT/'diagnostic-unsignaled-recipe.json').write_text(json.dumps(other_recipe,indent=2)+'\n')
    print(json.dumps({'diagnostic_bytes':output.stat().st_size,'sha256':checksum,
                      'unsignaled_bytes':other.stat().st_size,'frames':len(trace)}))


if __name__=='__main__':
    main()
