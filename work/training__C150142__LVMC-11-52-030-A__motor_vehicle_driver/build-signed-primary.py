"""Package the first signed red-curb case without changing ordinary receipts."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
NATIVE = ROOT / 'native'
sys.path.insert(0, str(NATIVE))
import exception_road


def encode(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def build():
    case_id = ROOT.name + '__ordinary_red_signed'
    cases = json.loads((ROOT / 'exception-case-matrix.json').read_text())['cases']
    case = next(item for item in cases if item['case_id'] == case_id)
    if case['requested_stationary_duration_s'] != 12 or case['service_class'] != 'ordinary':
        raise ValueError('Signed-case source definition changed')
    base = json.loads((ROOT / 'selected-primary/reference/construction.json').read_text())
    files = {item['path']: item['content'] for item in base['files']}
    road = exception_road.construct(case)
    if exception_road.readback(road)['sign_readback']['displayed_classes'] != ['no_parking']:
        raise ValueError('Signed road readback differs')
    files['red-curb-road.xodr'] = road
    for target, source in (
        ('runner.py', 'signed_runner.py'),
        ('finalize_selected.py', 'finalize_signed.py'),
        ('measure_exceptions.py', 'measure_exceptions.py'),
        ('exception_road.py', 'exception_road.py')):
        files[target] = (NATIVE / source).read_text()
    cfg = json.loads(files['config.json'])
    cfg.update(case_id=case_id, selected_case_id=case_id,
               supported_case_ids=[case_id], sign_classes=case['sign_classes'],
               service_class=case['service_class'],
               native_blueprint='vehicle.tesla.model3',
               road_sha256=digest(road))
    files['config.json'] = encode(cfg)
    base['case_id'] = case_id
    base['files'] = [{'path': path, 'content': content} for path, content in files.items()]
    base['status'] = 'draft_selected_cpu'
    base['recording_description']['limitations'].append(
        'Sign classes are authored OpenDRIVE; Native signal readback and pixels require separate review.')
    base['measurement_plan'] = {
        'source': 'retained Native body, velocity, red paint and signal readback',
        'finalizer': 'finalize_selected.py', 'legal_verdict': None}
    target = ROOT / 'selected-primary/ordinary_red_signed/construction.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(encode(base))
    return {'case_id': case_id, 'construction_sha256': digest(target.read_text()),
            'road_sha256': digest(road), 'files': len(files)}


if __name__ == '__main__':
    print(encode(build()), end='')
