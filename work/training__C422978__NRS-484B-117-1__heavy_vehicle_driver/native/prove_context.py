"""Synthetic spatial-context positives and altered-source controls for all bundles."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from measure_context import measure

HERE=Path(__file__).resolve().parent
CASES=('reference','contrast')
CANDIDATES=('primary','fallback1','fallback2','fallback3')


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def packet(folder):
    survey={'source_crs':'synthetic-local-metres',
            'city_boundary_polygon':[[-20,-20],[180,-20],[180,20],[-20,20]],
            'sidewalk_polygon':[[0,3.5],[140,3.5],[140,7.5],[0,7.5]],
            'entrance_polygons':[{'id':'synthetic-driveway-1','kind':'driveway',
                                  'polygon':[[50,3.5],[60,3.5],[60,7.5],[50,7.5]]}]}
    calibration={'source_crs':'synthetic-local-metres','native_to_context_affine':[[1,0,0],[0,1,0]]}
    (folder/'city-survey-source.geojson').write_text(json.dumps(survey,indent=2)+'\n')
    (folder/'city-calibration.json').write_text(json.dumps(calibration,indent=2)+'\n')
    return {'format':'c422978-heavy-spatial-context-v1','law_id':'NRS-484B-117-1',
            'authority_kind':'synthetic_cpu','city_authority_reviewed':False,
            'entrance_authority_reviewed':False,
            'map_readback_sha256':sha(folder/'native-map-readback.json'),
            'native_to_context_affine':[[1,0,0],[0,1,0]],
            'city_boundary_polygon':survey['city_boundary_polygon'],
            'sidewalk_polygon':survey['sidewalk_polygon'],
            'entrance_polygons':survey['entrance_polygons'],
            'source_provenance':{'source_sha256':sha(folder/'city-survey-source.geojson'),
                                 'calibration_sha256':sha(folder/'city-calibration.json'),
                                 'crs':'synthetic-local-metres',
                                 'calibration_source':'synthetic identity diagnostic'}}


def rejected(folder,path,changed):
    path.write_text(json.dumps(changed)+'\n')
    try: measure(folder,path)
    except (ValueError,TypeError,KeyError,ZeroDivisionError): return True
    raise AssertionError('Altered spatial context accepted')


def prove():
    positives=[];negatives=[]
    for case in CASES:
        for candidate in CANDIDATES:
            folder=HERE/'saved-fixtures'/case/candidate
            context=folder/'city-context.json'
            base=packet(folder)
            context.write_text(json.dumps(base,indent=2)+'\n')
            result=measure(folder,context)
            if result['source_kind']!='synthetic_cpu' or result['legal_verdict'] is not None or (case=='reference' and result['moving_city_sidewalk_outside_entrance_frames']!=0) or (case=='contrast' and result['moving_city_sidewalk_outside_entrance_frames']<300):
                raise AssertionError('Synthetic spatial positive differs')
            positives.append({'case':case,'candidate':candidate,'measurement':result})
            mutations={}
            bad=copy.deepcopy(base);bad['map_readback_sha256']='f'*64;mutations['map_binding']=bad
            bad=copy.deepcopy(base);bad['native_to_context_affine']=[[1,0,0],[2,0,0]];mutations['singular_transform']=bad
            bad=copy.deepcopy(base);bad['city_authority_reviewed']=True;mutations['false_authority']=bad
            bad=copy.deepcopy(base);bad['entrance_polygons'][0]['id']='';mutations['entrance_identity']=bad
            bad=copy.deepcopy(base);bad['source_provenance']['source_sha256']='0'*64;mutations['survey_binding']=bad
            with tempfile.TemporaryDirectory(dir=HERE) as temp:
                altered=Path(temp)/'city-context.json'
                for name,bad in mutations.items():
                    negatives.append({'case':case,'candidate':candidate,'mutation':name,
                                      'rejected':rejected(folder,altered,bad)})
    result={'format':'c422978-heavy-spatial-cpu-proof-v1',
            'processor_sha256':sha(HERE/'measure_context.py'),
            'positives':positives,'negatives':negatives,
            'original_city_authority_observed':False,'delivery_ready':False}
    (HERE/'context-proof.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    result=prove();print(json.dumps({'positives':len(result['positives']),'negatives':len(result['negatives'])}))
