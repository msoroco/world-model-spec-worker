"""Prepare a source-bound spatial packet for a saved heavy-vehicle Native attempt."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from measure_context import surveyed_polygons, transform, measure
from measure_saved import measure as measure_saved


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(attempt, survey_path, expected_survey_sha256, calibration_path, diagnostic=False):
    attempt, survey_path, calibration_path=map(Path,(attempt,survey_path,calibration_path))
    if sha(survey_path)!=expected_survey_sha256:
        raise ValueError('Survey source hash differs')
    saved=measure_saved(attempt)
    if diagnostic != (saved['source_kind']=='synthetic_cpu'):
        raise ValueError('Diagnostic flag and Native source provenance differ')
    survey=json.loads(survey_path.read_text())
    calibration=json.loads(calibration_path.read_text())
    if survey.get('source_crs')!=calibration.get('source_crs') or not survey.get('source_crs'):
        raise ValueError('Survey/calibration CRS differs')
    if survey.get('source_kind')!=('synthetic_cpu' if diagnostic else 'surveyed_city_source'):
        raise ValueError('Survey source provenance differs')
    if calibration.get('map_readback_sha256')!=sha(attempt/'native-map-readback.json'):
        raise ValueError('Calibration Native map readback differs')
    matrix=calibration.get('native_to_context_affine')
    transform([(0,0)],matrix)
    if not isinstance(calibration.get('calibration_source'),str) or not calibration['calibration_source']:
        raise ValueError('Calibration source absent')
    if not diagnostic:
        if matrix==[[1,0,0],[0,1,0]] or not isinstance(calibration.get('reviewed_control_points'),list) or len(calibration['reviewed_control_points'])<3:
            raise ValueError('Original survey requires nonidentity reviewed calibration')
    polygons=surveyed_polygons(survey)
    targets=[attempt/'city-survey-source.geojson',attempt/'city-calibration.json',attempt/'city-context.json']
    if any(path.exists() for path in targets):
        raise ValueError('Use a fresh spatial packet destination')
    packet={'format':'c422978-heavy-spatial-context-v1','law_id':'NRS-484B-117-1',
            'authority_kind':'synthetic_cpu' if diagnostic else 'unreviewed_survey',
            'city_authority_reviewed':False,'entrance_authority_reviewed':False,
            'map_readback_sha256':sha(attempt/'native-map-readback.json'),
            'native_to_context_affine':matrix,**polygons,
            'source_provenance':{'source_sha256':expected_survey_sha256,
                                 'calibration_sha256':sha(calibration_path),
                                 'crs':survey['source_crs'],
                                 'calibration_source':calibration['calibration_source']}}
    shutil.copyfile(survey_path,targets[0]);shutil.copyfile(calibration_path,targets[1])
    targets[2].write_text(json.dumps(packet,indent=2,allow_nan=False)+'\n')
    result=measure(attempt,targets[2])
    return {'packet_path':str(targets[2]),'measurement':result}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--attempt',required=True);p.add_argument('--survey',required=True)
    p.add_argument('--survey-sha256',required=True);p.add_argument('--calibration',required=True)
    p.add_argument('--diagnostic',action='store_true')
    a=p.parse_args()
    print(json.dumps(prepare(a.attempt,a.survey,a.survey_sha256,a.calibration,a.diagnostic),indent=2))
