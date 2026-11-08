"""Fresh-packet preparation proof across all heavy-vehicle CPU candidates."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from prepare_context import prepare

HERE=Path(__file__).resolve().parent
CASES=('reference','contrast');CANDIDATES=('primary','fallback1','fallback2','fallback3')
SPATIAL=('city-context.json','city-survey-source.geojson','city-calibration.json')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def rejected(fn):
    try:fn()
    except ValueError:return True
    raise AssertionError('Altered spatial preparation accepted')


def prove():
    positives=[];negatives=[]
    for case in CASES:
        for candidate in CANDIDATES:
            original=HERE/'saved-fixtures'/case/candidate
            survey=original/'city-survey-source.geojson';calibration=original/'city-calibration.json'
            with tempfile.TemporaryDirectory(dir=HERE) as temporary:
                copy=Path(temporary)/'attempt';shutil.copytree(original,copy)
                for name in SPATIAL:(copy/name).unlink()
                result=prepare(copy,survey,sha(survey),calibration,True)
                if result['measurement']['frames']!=480 or result['measurement']['authority_kind']!='synthetic_cpu':
                    raise AssertionError('Prepared synthetic packet differs')
                for name in SPATIAL:
                    if (copy/name).read_bytes()!=(original/name).read_bytes():
                        raise AssertionError('Prepared packet bytes differ')
                positives.append({'case':case,'candidate':candidate,
                                  'packet_sha256':sha(copy/'city-context.json'),
                                  'outside_entrance_frames':result['measurement']['moving_city_sidewalk_outside_entrance_frames']})
                negatives.append({'case':case,'candidate':candidate,'mutation':'existing_destination',
                                  'rejected':rejected(lambda:prepare(copy,survey,sha(survey),calibration,True))})
            with tempfile.TemporaryDirectory(dir=HERE) as temporary:
                copy=Path(temporary)/'attempt';shutil.copytree(original,copy)
                for name in SPATIAL:(copy/name).unlink()
                negatives.append({'case':case,'candidate':candidate,'mutation':'survey_hash',
                                  'rejected':rejected(lambda:prepare(copy,survey,'0'*64,calibration,True))})
                negatives.append({'case':case,'candidate':candidate,'mutation':'original_scope_identity_calibration',
                                  'rejected':rejected(lambda:prepare(copy,survey,sha(survey),calibration,False))})
                changed=Path(temporary)/'bad-calibration.json'
                bad=json.loads(calibration.read_text());bad['map_readback_sha256']='f'*64
                changed.write_text(json.dumps(bad)+'\n')
                negatives.append({'case':case,'candidate':candidate,'mutation':'calibration_map_hash',
                                  'rejected':rejected(lambda:prepare(copy,survey,sha(survey),changed,True))})
    proof={'format':'c422978-heavy-spatial-preparation-proof-v1',
           'preparer_sha256':sha(HERE/'prepare_context.py'),
           'processor_sha256':sha(HERE/'measure_context.py'),
           'positives':positives,'negatives':negatives,
           'original_survey_prepared':False,'delivery_ready':False}
    (HERE/'context-preparation-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof

if __name__=='__main__':
    result=prove();print(json.dumps({'positives':len(result['positives']),'negatives':len(result['negatives'])}))
