"""Independent fixed-condition and 500-foot source comparison for 407."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from u_turn_407_geometry import validate_geometry_packet

HERE=Path(__file__).resolve().parent
def read(name):return json.loads((HERE/name).read_text())


def audit(base=None,candidate=None,base_diagnostic=None,candidate_diagnostic=None):
    base=deepcopy(base or read('construction.json'))
    candidate=deepcopy(candidate or read('construction-prohibition_407.json'))
    base_diagnostic=deepcopy(base_diagnostic or read('diagnostic-safety_clear.json'))
    candidate_diagnostic=deepcopy(candidate_diagnostic or read('diagnostic-prohibition_407.json'))
    if (not base['case_id'].endswith('__safety_clear') or
            not candidate['case_id'].endswith('__prohibition_407') or
            (base['law_id'],base['cell_id'],base['actor']) !=
            (candidate['law_id'],candidate['cell_id'],candidate['actor'])):
        raise ValueError('407 comparison identity differs')
    left=json.loads(next(item['content'] for item in base['files'] if item['path']=='config.json'))
    right=json.loads(next(item['content'] for item in candidate['files'] if item['path']=='config.json'))
    if (left['engineering'] != right['engineering'] or
            left['cameras'] != right['cameras'] or
            left['required_atoms'] != right['required_atoms']):
        raise ValueError('407 route, participants or cameras differ')
    old,new=base_diagnostic['files'],candidate_diagnostic['files']
    common=set(old)&set(new)
    if (set(new)-set(old) != {'u_turn_407_geometry.json'} or
            any(old[name]!=new[name] for name in
                common-{'u_turn_fixture_provenance.json','capture/evidence.jsonl'}) or
            base_diagnostic['videos']!=candidate_diagnostic['videos'] or
            base_diagnostic['graphs']!=candidate_diagnostic['graphs']):
        raise ValueError('407 diagnostic motion, cameras or map source differs')
    geometry=json.loads(new['u_turn_407_geometry.json'])
    context=json.loads(new['u_turn_context.json'])
    validate_geometry_packet(geometry,context)
    original=[json.loads(line) for line in old['capture/evidence.jsonl'].splitlines()]
    observed=[json.loads(line) for line in new['capture/evidence.jsonl'].splitlines()]
    if len(original)!=len(observed) or not observed:
        raise ValueError('407 original visibility frame inventory differs')
    horizons=set()
    for before,after in zip(original,observed):
        packet=after.pop('visibility',None)
        before.pop('visibility',None)
        if before!=after or not isinstance(packet,dict) or packet.get('method')!='actual_actor_body_raycast_v2' or packet.get('probe_distance_m')!=152.4 or set(packet.get('required_lane_ids',[]))!={-1,1}:
            raise ValueError('407 visibility source or fixed frame differs')
        approaches=packet.get('approaches')
        if not isinstance(approaches,list) or {a.get('lane_id') for a in approaches}!={-1,1}:
            raise ValueError('407 both incoming visibility directions missing')
        for a in approaches:
            rays=a.get('body_rays_at_probe')
            horizon=a.get('any_body_sight_horizon',{}).get('distance_m')
            if (not isinstance(rays,list) or len(rays)!=9 or
                    any(type(ray.get('clear')) is not bool for ray in rays) or
                    a.get('any_sample_clear_at_probe') is not any(ray['clear'] for ray in rays) or
                    horizon not in (152.0,152.4,152.8)):
                raise ValueError('407 nine-body-ray boundary source differs')
            horizons.add(horizon)
    if horizons!={152.0,152.4,152.8}:
        raise ValueError('407 below/at/above 500 ft probes missing')
    return {'comparison_id':'prohibition_407',
            'case_ids':[base['case_id'],candidate['case_id']],
            'fixed_conditions_verified':True,
            'boundary_probe_m':sorted(horizons),
            'physical_occlusion_verified':False,'legal_visibility_judgment':None}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--package');args=parser.parse_args()
    if args.package and Path(args.package).resolve()!=HERE:raise ValueError('Wrong 407 package')
    print(json.dumps(audit(),sort_keys=True))


if __name__=='__main__':main()
