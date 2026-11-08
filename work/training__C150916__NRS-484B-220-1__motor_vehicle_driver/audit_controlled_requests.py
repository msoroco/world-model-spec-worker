"""Independent 1,920-row audit of four one-way request pairs."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parent
NATIVE=CASE/'native'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    proof_path=CASE/'controlled-request-comparison.json'
    proof=json.loads(proof_path.read_text())
    if (proof['format']!='c150916-controlled-request-comparison-v1' or
            proof['assignment_id']!=CASE.name or proof['road_sha256']!=sha(NATIVE/'road.xodr') or
            proof['construction_manifest_sha256']!=sha(NATIVE/'drafts'/'manifest.json') or
            proof['original_native_observed'] or proof['accepted_comparison'] or
            proof['legal_verdict'] is not None or proof['delivery_ready'] or
            len(proof['pairs'])!=4 or
            [item['mutation'] for item in proof['negative_controls']]!=
            ['ego_speed','lane','heading','mirror_position'] or
            not all(item['rejected'] is True for item in proof['negative_controls'])):
        raise ValueError('One-way comparison proof provenance or scope differs')
    seen=set();checked=0
    for pair in proof['pairs']:
        candidate=pair['candidate_id']
        if candidate not in ('primary','fallback1','fallback2','fallback3') or candidate in seen:
            raise ValueError('One-way comparison candidate coverage differs')
        seen.add(candidate)
        first=NATIVE/'drafts'/'designated'/candidate/'requested-tracks.jsonl'
        second=NATIVE/'drafts'/'opposite'/candidate/'requested-tracks.jsonl'
        if pair['designated_sha256']!=sha(first) or pair['opposite_sha256']!=sha(second):
            raise ValueError('One-way paired request source differs')
        forward=[json.loads(line) for line in first.read_text().splitlines()]
        reverse=[json.loads(line) for line in second.read_text().splitlines()]
        if len(forward)!=240 or len(reverse)!=240:raise ValueError('One-way paired rows differ')
        for i in range(240):
            a,b=forward[i],reverse[i]
            if (a['frame']!=i or b['frame']!=i or
                    a['time_s']!=b['time_s'] or a['ego_speed_mps']!=b['ego_speed_mps'] or
                    a['ego_y_m']!=b['ego_y_m'] or a['lane_id']!=b['lane_id'] or
                    a['ego_heading_deg']!=0 or b['ego_heading_deg']!=180 or
                    round((a['ego_x_m']+b['ego_x_m'])/2,3)!=100):
                raise ValueError('One-way paired fixed fields or mirror differ')
        metric={'frames':240,'longitudinal_mirror_center_x_m':100,
                'forward_signed_displacement_m':round(forward[-1]['ego_x_m']-forward[0]['ego_x_m'],3),
                'reverse_signed_displacement_m':round(reverse[-1]['ego_x_m']-reverse[0]['ego_x_m'],3)}
        if metric!=pair['metric'] or metric['forward_signed_displacement_m']!=-metric['reverse_signed_displacement_m']:
            raise ValueError('One-way independent pair metric differs')
        checked+=480
    if checked!=1920:raise ValueError('One-way pair coverage incomplete')
    result={'format':'c150916-independent-request-comparison-audit-v1',
            'proof_sha256':sha(proof_path),'paired_rows_checked':checked,
            'negative_controls_checked':4,'original_native_observed':False,
            'accepted_comparison':False,'delivery_ready':False}
    (CASE/'controlled-request-comparison-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(audit()))
