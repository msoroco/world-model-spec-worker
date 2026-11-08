"""Independently recompute four paired heavy-vehicle synthetic comparisons."""
import hashlib
import json
from pathlib import Path

CASE = Path(__file__).resolve().parent
NATIVE = CASE/'native'
CANDIDATES = ('primary','fallback1','fallback2','fallback3')
MUTATIONS = ('longitudinal_center','speed','native_frame','body_x',
             'changed_survey','changed_exception_fact')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit():
    proof_path = CASE/'controlled-comparison.json'
    proof = json.loads(proof_path.read_text())
    if (proof['format'] != 'c422978-heavy-controlled-synthetic-comparison-v1' or
            proof['saved_proof_sha256'] != sha(NATIVE/'saved-proof.json') or
            proof['context_proof_sha256'] != sha(NATIVE/'context-proof.json') or
            proof['exception_proof_sha256'] != sha(NATIVE/'exception-proof.json') or
            len(proof['pairs']) != 4 or len(proof['negatives']) != 24 or
            proof['original_native_observed'] or proof['accepted_comparison'] or
            proof['legal_verdict'] is not None or proof['delivery_ready']):
        raise ValueError('Controlled comparison proof scope differs')
    seen, total_rows = set(), 0
    for pair in proof['pairs']:
        candidate = pair['candidate']
        if candidate not in CANDIDATES or candidate in seen:
            raise ValueError('Controlled comparison candidate differs')
        seen.add(candidate)
        ref_path = NATIVE/'saved-fixtures/reference'/candidate/'native-observed.jsonl'
        con_path = NATIVE/'saved-fixtures/contrast'/candidate/'native-observed.jsonl'
        if pair['reference_sha256'] != sha(ref_path) or pair['contrast_sha256'] != sha(con_path):
            raise ValueError('Controlled saved-source hash differs')
        ref_folder,con_folder=ref_path.parent,con_path.parent
        for name,key in (('city-survey-source.geojson','survey_sha256'),
                         ('city-calibration.json','calibration_sha256'),
                         ('authority/synthetic-exception-source.json','exception_document_sha256')):
            if sha(ref_folder/name)!=pair[key] or sha(con_folder/name)!=pair[key]:
                raise ValueError('Controlled paired spatial or exception source differs')
        for name in ('native-map-readback.json','city-context.json'):
            if sha(ref_folder/name)!=sha(con_folder/name):
                raise ValueError('Controlled paired map or context differs')
        source=json.loads((ref_folder/'city-survey-source.geojson').read_text())
        if (source['type']!='FeatureCollection' or source['source_kind']!='synthetic_cpu' or
                {row['id'] for row in source['features']}!={'city_boundary','sidewalk','driveway:synthetic-1'}):
            raise ValueError('Controlled survey feature set differs')
        facts=[]
        for folder in (ref_folder,con_folder):
            packet=json.loads((folder/'exception-evidence.json').read_text())
            if (packet['review_status']!='pending_independent_review' or
                    packet['native_capture_report_sha256']!=sha(folder/'native-capture-report.json') or
                    packet['native_map_readback_sha256']!=sha(folder/'native-map-readback.json') or
                    any(row['value'] is not False or row['reviewed'] is not False or
                        row['document_sha256']!=pair['exception_document_sha256']
                        for row in packet['facts'].values())):
                raise ValueError('Controlled exception fact packet differs')
            facts.append({key:row['value'] for key,row in packet['facts'].items()})
        if facts[0]!=facts[1]:
            raise ValueError('Controlled reported facts differ')
        ref, con = lines(ref_path),lines(con_path)
        if len(ref)!=480 or len(con)!=480:
            raise ValueError('Controlled saved-source frame count differs')
        ref_hits, con_hits, con_inside = [], [], []
        ref_outside,con_outside=[],[]
        for index,(a,b) in enumerate(zip(ref,con)):
            if (a['frame']!=index or b['frame']!=index or
                    a['native_frame']!=b['native_frame'] or
                    a['time_s']!=b['time_s'] or a['vehicle_blueprint']!=b['vehicle_blueprint'] or
                    a['speed_mps']!=b['speed_mps'] or
                    a['center_native_xy_m'][0]!=b['center_native_xy_m'][0] or
                    [p[0] for p in a['body_native_xy_m']] != [p[0] for p in b['body_native_xy_m']]):
                raise ValueError('Controlled paired field differs')
            ay=[p[1] for p in a['body_native_xy_m']]
            by=[p[1] for p in b['body_native_xy_m']]
            if a['speed_mps']>.1 and min(ay)<7.5 and max(ay)>3.5: ref_hits.append(index)
            if b['speed_mps']>.1 and min(by)<7.5 and max(by)>3.5: con_hits.append(index)
            if b['speed_mps']>.1 and min(by)>=3.5 and max(by)<=7.5: con_inside.append(index)
            for row,dest in ((a,ref_outside),(b,con_outside)):
                x=[p[0] for p in row['body_native_xy_m']]
                y=[p[1] for p in row['body_native_xy_m']]
                on_sidewalk=max(x)>=0 and min(x)<=140 and max(y)>=3.5 and min(y)<=7.5
                in_city=max(x)>=-20 and min(x)<=180 and max(y)>=-20 and min(y)<=20
                on_entrance=max(x)>=50 and min(x)<=60 and max(y)>=3.5 and min(y)<=7.5
                if row['speed_mps']>.1 and on_sidewalk and in_city and not on_entrance:
                    dest.append(index)
            total_rows += 2
        expected = {'reference_moving_overlap_frames':len(ref_hits),
                    'contrast_moving_overlap_frames':len(con_hits),
                    'contrast_first_overlap_frame':con_hits[0] if con_hits else None,
                    'contrast_full_body_inside_frames':len(con_inside),
                    'contrast_minus_reference_overlap_frames':len(con_hits)-len(ref_hits),
                    'reference_city_sidewalk_outside_entrance_frames':len(ref_outside),
                    'contrast_city_sidewalk_outside_entrance_frames':len(con_outside),
                    'reported_exception_pattern':False}
        if pair['metric'] != expected or ref_hits or len(con_hits)<390 or ref_outside or len(con_outside)<300:
            raise ValueError('Controlled comparison metric differs')
    if seen != set(CANDIDATES) or {(n['candidate'],n['mutation']) for n in proof['negatives']} != {
            (candidate,mutation) for candidate in CANDIDATES for mutation in MUTATIONS} or \
            not all(n['rejected'] is True for n in proof['negatives']):
        raise ValueError('Controlled comparison negative coverage differs')
    result={'format':'c422978-heavy-independent-comparison-audit-v1',
            'proof_sha256':sha(proof_path),'candidate_pairs':len(seen),
            'saved_rows_recomputed':total_rows,'recorded_negative_rejections':len(proof['negatives']),
            'accepted_comparison':False,'delivery_ready':False}
    (CASE/'controlled-comparison-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    result=audit()
    print(json.dumps({'pairs':result['candidate_pairs'],
                      'rows':result['saved_rows_recomputed'],
                      'negatives':result['recorded_negative_rejections']}))
