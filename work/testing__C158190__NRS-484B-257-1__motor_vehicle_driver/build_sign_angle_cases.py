"""Construct exact authored sign-angle drafts without changing selected cases."""

import hashlib
import json
from pathlib import Path

from build_through_speed_cases import replace_strings

ROOT = Path(__file__).resolve().parent
PREFIX = ROOT.name + '__'
OLD = 'yield_nearest_view_through_approaches'
ANGLES_RAD = ((-0.15, 'minus_015'), (0.0, 'zero'), (0.15, 'plus_015'))


def build():
    template = json.loads((ROOT / 'construction.json').read_text())
    cases = []
    for angle, label in ANGLES_RAD:
        suffix = f'yield_nearest_view_sign_angle_{label}'
        draft = replace_strings(template, OLD, suffix)
        files = {item['path']: item for item in draft['files']}
        road = files['native-map-plan/yield-nearest-view.xodr']
        anchor = 'hOffset="0"'
        assert road['content'].count(anchor) == 1
        road['content'] = road['content'].replace(anchor, f'hOffset="{angle:.2f}"')
        config = json.loads(files['config.json']['content'])
        assert config['selected_case_id'] == PREFIX + suffix
        assert config['supported_case_ids'][0] == PREFIX + suffix
        draft['files'].append({'path': 'tests/test_sign_angle.py', 'content':
            'import unittest\nimport xml.etree.ElementTree as ET\nfrom pathlib import Path\n'
            'from yield_site import validate_authored_site\n\n'
            'class SignAngleTests(unittest.TestCase):\n'
            '    def test_authored_sign_angle(self):\n'
            '        road = Path(__file__).resolve().parents[1] / "native-map-plan/yield-nearest-view.xodr"\n'
            '        validate_authored_site(road)\n'
            '        sign = ET.parse(road).getroot().find("./road[@id=\'158190\']/signals/signal")\n'
            f'        self.assertAlmostEqual(float(sign.attrib["hOffset"]), {angle:.2f})\n'})
        path = ROOT / f'cases/sign_angle_{label}/construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(draft, indent=2) + '\n')
        cases.append({'case_id': PREFIX + suffix,
                      'construction': str(path.relative_to(ROOT)),
                      'construction_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'kind': 'diagnostic_unselected',
                      'authored_sign_hOffset_rad': angle})
    manifest = {'format': 'worker-execution-manifest-draft',
                'assignment_id': ROOT.name, 'cases': cases,
                'limitation': 'Authored sign angle only; Native sign pose and original pixels unverified.'}
    (ROOT / 'sign-angle-draft-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'draft_cases': len(cases), 'angles_rad': [angle for angle, _ in ANGLES_RAD]}))


if __name__ == '__main__':
    build()
