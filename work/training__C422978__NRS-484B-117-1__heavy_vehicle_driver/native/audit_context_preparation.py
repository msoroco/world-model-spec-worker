"""Independent audit of fresh surveyed-context packet preparation."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from prepare_context import prepare
from measure_context import surveyed_polygons

HERE=Path(__file__).resolve().parent
CASES=('reference','contrast');CANDIDATES=('primary','fallback1','fallback2','fallback3')
SPATIAL=('city-context.json','city-survey-source.geojson','city-calibration.json')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    proof=json.loads((HERE/'context-preparation-proof.json').read_text())
    if proof['preparer_sha256']!=sha(HERE/'prepare_context.py') or proof['processor_sha256']!=sha(HERE/'measure_context.py') or proof['original_survey_prepared'] or proof['delivery_ready']:
        raise ValueError('Preparation code identity differs')
    positives={(p['case'],p['candidate']):p for p in proof['positives']}
    negatives={(n['case'],n['candidate'],n['mutation']) for n in proof['negatives'] if n['rejected'] is True}
    expected={(case,candidate) for case in CASES for candidate in CANDIDATES}
    if set(positives)!=expected or negatives!={(case,candidate,mutation) for case,candidate in expected for mutation in ('existing_destination','survey_hash','original_scope_identity_calibration','calibration_map_hash')}:
        raise ValueError('Preparation proof coverage differs')
    frames=0
    for case,candidate in expected:
        original=HERE/'saved-fixtures'/case/candidate
        source=original/'city-survey-source.geojson'
        survey=json.loads(source.read_text())
        packet=json.loads((original/'city-context.json').read_text())
        geometry=surveyed_polygons(survey)
        if any(packet[key]!=geometry[key] for key in geometry):
            raise ValueError('Prepared survey geometry differs')
        if packet['source_provenance']['source_sha256']!=sha(source) or packet['source_provenance']['calibration_sha256']!=sha(original/'city-calibration.json'):
            raise ValueError('Prepared source hash differs')
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            dest=Path(temporary)/'attempt';shutil.copytree(original,dest)
            for name in SPATIAL:(dest/name).unlink()
            output=prepare(dest,source,sha(source),original/'city-calibration.json',True)
            if sha(dest/'city-context.json')!=positives[(case,candidate)]['packet_sha256'] or output['measurement']['moving_city_sidewalk_outside_entrance_frames']!=positives[(case,candidate)]['outside_entrance_frames']:
                raise ValueError('Fresh preparation does not reproduce retained proof')
            frames+=output['measurement']['frames']
    if frames!=3840:raise ValueError('Prepared row coverage differs')
    result={'format':'c422978-heavy-spatial-preparation-audit-v1',
            'positives':8,'negatives':32,'rows_replayed':frames,
            'proof_sha256':sha(HERE/'context-preparation-proof.json'),
            'original_survey_prepared':False,'delivery_ready':False}
    (HERE/'context-preparation-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
