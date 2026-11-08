"""Independent 1,920-row rotary request-pair audit."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parent
NATIVE=CASE/'native'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    path=CASE/'controlled-request-comparison.json'
    proof=json.loads(path.read_text())
    if (proof['format']!='c234827-controlled-request-comparison-v1' or
            proof['assignment_id']!=CASE.name or
            proof['road_sha256']!=sha(NATIVE/'road.xodr') or
            proof['island_geometry_sha256']!=sha(NATIVE/'island-geometry.json') or
            proof['construction_manifest_sha256']!=sha(NATIVE/'drafts'/'manifest.json') or
            proof['original_native_observed'] or proof['physical_island_verified'] or
            proof['accepted_comparison'] or proof['legal_verdict'] is not None or
            proof['delivery_ready'] or
            [row['mutation'] for row in proof['negative_controls']]!=
            ['speed','lane','mirror_position','heading'] or
            not all(row['rejected'] is True for row in proof['negative_controls'])):
        raise ValueError('Rotary comparison source or limit differs')
    seen=set();count=0
    for pair in proof['pairs']:
        candidate=pair['candidate_id']
        if candidate not in ('primary','fallback1','fallback2','fallback3') or candidate in seen:
            raise ValueError('Rotary pair coverage differs')
        seen.add(candidate)
        first=NATIVE/'drafts'/'reference'/candidate/'requested-tracks.jsonl'
        second=NATIVE/'drafts'/'contrast'/candidate/'requested-tracks.jsonl'
        if pair['reference_sha256']!=sha(first) or pair['contrast_sha256']!=sha(second):
            raise ValueError('Rotary paired source differs')
        a=[json.loads(line) for line in first.read_text().splitlines()]
        b=[json.loads(line) for line in second.read_text().splitlines()]
        if len(a)!=240 or len(b)!=240:
            raise ValueError('Rotary pair rows differ')
        for i,(left,right) in enumerate(zip(a,b)):
            heading_sum=(left['ego_heading_deg']+right['ego_heading_deg'])%360
            if (left['frame']!=i or right['frame']!=i or
                    left['time_s']!=right['time_s'] or
                    left['ego_speed_mps']!=right['ego_speed_mps'] or
                    left['lane_id']!=right['lane_id'] or
                    left['requested_radius_m']!=right['requested_radius_m'] or
                    left['island_center_xy_m']!=[0,0] or
                    right['island_center_xy_m']!=[0,0] or
                    abs(left['ego_x_m']-right['ego_x_m'])>1e-5 or
                    abs(left['ego_y_m']+right['ego_y_m'])>1e-5 or
                    min(heading_sum,360-heading_sum)>1e-4):
                raise ValueError('Rotary independent fixed fields or mirror differ')
            count+=2
        if pair['metric']!={'frames':240,'fixed_ring_and_speed':True,
                'mirrored_lateral_position':True,
                'reference_island_side_request':'left',
                'contrast_island_side_request':'right'}:
            raise ValueError('Rotary pair metric differs')
    if seen!={'primary','fallback1','fallback2','fallback3'} or count!=1920:
        raise ValueError('Rotary comparison coverage incomplete')
    result={'format':'c234827-independent-request-comparison-audit-v1',
            'proof_sha256':sha(path),'paired_rows_checked':count,
            'negative_controls_checked':4,
            'original_native_observed':False,
            'accepted_comparison':False,'delivery_ready':False}
    (CASE/'controlled-request-comparison-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(audit()))
