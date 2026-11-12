"""Verify sign-angle drafts differ only by exact ID and authored hOffset."""

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from build_sign_angle_cases import ANGLES_RAD

ROOT = Path(__file__).resolve().parent


def main():
    manifest = json.loads((ROOT / 'sign-angle-draft-manifest.json').read_text())
    assert len(manifest['cases']) == len(ANGLES_RAD)
    snapshots = []
    receipts = []
    for (angle, label), case in zip(ANGLES_RAD, manifest['cases']):
        path = ROOT / case['construction']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == case['construction_sha256']
        draft = json.loads(path.read_text())
        assert draft['case_id'] == case['case_id']
        files = {item['path']: item['content'] for item in draft['files']}
        road = files['native-map-plan/yield-nearest-view.xodr']
        sign = ET.fromstring(road).find("./road[@id='158190']/signals/signal")
        assert sign is not None and abs(float(sign.attrib['hOffset']) - angle) < 1e-12
        assert (sign.attrib['type'], sign.attrib['orientation'], sign.attrib['s']) == ('205', '+', '60')
        materialized = ROOT.parents[1] / f'.runtime-work/c158190-sign-angle-{label}-offline-v3'
        assert (materialized / 'native-map-plan/yield-nearest-view.xodr').read_text() == road
        offline = (materialized / 'offline.log').read_text()
        assert 'Ran 36 tests' in offline and 'OK' in offline
        assert "'native_rotation_deg'" in files['yield_control_sources.py']
        assert "float(transform.rotation.yaw)" in files['yield_control_sources.py']
        assert "row['yield_sign']['native_rotation_deg']" in files['tests/test_yield_control_sources.py']
        assert 'test_rejects_nonfinite_native_rotation' in files['tests/test_yield_control_sources.py']
        snapshot = {}
        for name, content in files.items():
            if name == 'tests/test_sign_angle.py':
                continue
            if name == 'native-map-plan/yield-nearest-view.xodr':
                content = content.replace(f'hOffset="{angle:.2f}"', 'hOffset="ANGLE"')
            snapshot[name] = content.replace(f'yield_nearest_view_sign_angle_{label}',
                                             'SIGN_CASE')
        snapshots.append(snapshot)
        log = ROOT / f'cases/sign_angle_{label}/offline.log'
        receipts.append({'case_id': case['case_id'], 'authored_hOffset_rad': angle,
                         'construction_sha256': case['construction_sha256'],
                         'offline_log_sha256': hashlib.sha256(log.read_bytes()).hexdigest(),
                         'materialized_test_count': 36})
    assert snapshots[0] == snapshots[1] == snapshots[2]
    receipt = {'format': 'c158190-sign-angle-exact-offline-proof',
               'cases': receipts, 'only_case_id_and_authored_angle_vary': True,
               'native_sign_readback_implemented_and_cpu_tested': True,
               'native_sign_readback_proven': False,
               'original_pixel_face_check_proven': False}
    (ROOT / 'sign-angle-exact-offline-proof.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'exact_cases': 3, 'offline_tests_each': 36}))


if __name__ == '__main__':
    main()
