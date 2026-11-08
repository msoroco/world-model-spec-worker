"""Independent row-level audit of synthetic heavy-vehicle spatial context."""
import hashlib
import json
from pathlib import Path
from measure_saved import records
from measure_context import measure

HERE=Path(__file__).resolve().parent
CASES=('reference','contrast')
CANDIDATES=('primary','fallback1','fallback2','fallback3')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    proof=json.loads((HERE/'context-proof.json').read_text())
    if proof['processor_sha256']!=sha(HERE/'measure_context.py') or len(proof['positives'])!=8 or len(proof['negatives'])!=40 or proof['delivery_ready'] or proof['original_city_authority_observed']:
        raise ValueError('Spatial proof identity or coverage differs')
    index={(p['case'],p['candidate']):p['measurement'] for p in proof['positives']}
    negative={(n['case'],n['candidate'],n['mutation']) for n in proof['negatives'] if n['rejected'] is True}
    checked=0
    for case in CASES:
        for candidate in CANDIDATES:
            folder=HERE/'saved-fixtures'/case/candidate
            context=folder/'city-context.json'
            packet=json.loads(context.read_text())
            if packet['authority_kind']!='synthetic_cpu' or packet['city_authority_reviewed'] or packet['entrance_authority_reviewed'] or packet['native_to_context_affine']!=[[1,0,0],[0,1,0]] or packet['map_readback_sha256']!=sha(folder/'native-map-readback.json'):
                raise ValueError('Synthetic spatial packet differs')
            if packet['source_provenance']['source_sha256']!=sha(folder/'city-survey-source.geojson') or packet['source_provenance']['calibration_sha256']!=sha(folder/'city-calibration.json'):
                raise ValueError('Spatial source bytes differ')
            expected={'moving_sidewalk_intersection_frames':0,'moving_city_intersection_frames':0,
                      'moving_entrance_intersection_frames':0,'moving_city_sidewalk_outside_entrance_frames':0}
            outside=[]; touched=set()
            for row in records(folder/'native-observed.jsonl'):
                checked+=1
                if row['source_kind']!='synthetic_cpu':raise ValueError('Synthetic actor provenance differs')
                if row['speed_mps']<=.1:continue
                body=row['body_native_xy_m']
                xmin=min(p[0] for p in body);xmax=max(p[0] for p in body)
                ymin=min(p[1] for p in body);ymax=max(p[1] for p in body)
                city=xmax>=-20 and xmin<=180 and ymax>=-20 and ymin<=20
                sidewalk=xmax>=0 and xmin<=140 and ymax>=3.5 and ymin<=7.5
                entrance=xmax>=50 and xmin<=60 and ymax>=3.5 and ymin<=7.5
                if city:expected['moving_city_intersection_frames']+=1
                if sidewalk:expected['moving_sidewalk_intersection_frames']+=1
                if entrance:expected['moving_entrance_intersection_frames']+=1;touched.add('synthetic-driveway-1')
                if city and sidewalk and not entrance:
                    expected['moving_city_sidewalk_outside_entrance_frames']+=1;outside.append(row['frame'])
            actual=measure(folder,context)
            if actual!=index[(case,candidate)] or any(actual[k]!=v for k,v in expected.items()) or actual['first_outside_entrance_frame']!=(outside[0] if outside else None) or actual['touched_entrance_ids']!=sorted(touched) or actual['source_hashes']['city-context.json']!=sha(context) or actual['legal_verdict'] is not None:
                raise ValueError('Independent spatial row audit differs')
            for mutation in ('map_binding','singular_transform','false_authority','entrance_identity','survey_binding'):
                if (case,candidate,mutation) not in negative:raise ValueError('Spatial negative missing')
    if checked!=3840:raise ValueError('Spatial actor frame coverage differs')
    result={'format':'c422978-heavy-spatial-independent-audit-v1','positive_count':8,'negative_count':40,
            'rows_checked':checked,'proof_sha256':sha(HERE/'context-proof.json'),
            'original_city_authority_observed':False,'delivery_ready':False}
    (HERE/'context-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
