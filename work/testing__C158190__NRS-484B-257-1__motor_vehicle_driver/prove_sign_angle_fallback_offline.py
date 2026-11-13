"""Pin exact sign-angle fallback constructions and CPU offline outcomes."""

import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime'))
from scenario_pipeline.worker_exchange.candidate_constructions import validate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((ROOT / 'sign-angle-compatibility-manifest.json').read_text())
    proofs = []
    for entry in manifest['cases']:
        structure = validate(ROOT, entry, 'NRS-484B-257-1', 'C158190',
                             required=False, require_alternate=True, candidate_count=4)
        label = entry['case_id'].split('sign_angle_')[1]
        angle = entry['authored_sign_hOffset_rad']
        for candidate in entry['candidates']:
            ident = candidate['id']
            source = ROOT / candidate['construction']
            if sha(source) != candidate['construction_sha256']:
                raise ValueError('Candidate construction hash changed')
            construction = json.loads(source.read_text())
            files = {item['path']: item['content'] for item in construction['files']}
            road = ET.fromstring(files['native-map-plan/yield-nearest-view.xodr'])
            sign = road.find("./road[@id='158190']/signals/signal")
            if abs(float(sign.attrib['hOffset']) - angle) > 1e-12:
                raise ValueError('Fallback changed exact authored angle')
            if ident == 'fallback1':
                if float(sign.attrib['t']) != -3.4:
                    raise ValueError('Lateral sign correction absent')
            elif ident == 'fallback2':
                if "'reference_corner': pose(23, -28, 18, 135, -27)" not in files['runner.py']:
                    raise ValueError('Source-camera correction absent')
            elif ident == 'fallback3':
                if 'EGO_POINT = opendrive_to_carla(-70.0, -1.8)' not in files['yield_construction.py']:
                    raise ValueError('Approach-spawn correction absent')
            else:
                raise ValueError('Unknown candidate')
            output = REPO / f'.runtime-work/c158190-sign-angle-{label}-{ident}-offline-v1'
            offline = output / 'offline.log'
            expected = 37 if ident == 'fallback2' else 36
            if f'Ran {expected} tests' not in offline.read_text() or 'OK' not in offline.read_text():
                raise ValueError('Exact fallback CPU tests failed')
            returned = ROOT / f'cases/sign_angle_{label}/fallbacks/{ident}-offline.log'
            if not returned.is_file():
                raise ValueError('Returned offline command log missing')
            proofs.append({'case_id': entry['case_id'], 'candidate_id': ident,
                           'construction_sha256': sha(source),
                           'offline_log_sha256': sha(offline),
                           'returned_command_log_sha256': sha(returned),
                           'offline_test_count': expected})
        if structure['fallbacks'] != ['fallback1', 'fallback2', 'fallback3']:
            raise ValueError('Candidate structure differs')
    print(json.dumps({'format': 'c158190-sign-angle-fallback-offline-proof',
                      'fallbacks': proofs, 'all_passed': len(proofs) == 9,
                      'native_feasibility_proven': False,
                      'original_pixel_face_proven': False}, indent=2))


if __name__ == '__main__':
    main()
