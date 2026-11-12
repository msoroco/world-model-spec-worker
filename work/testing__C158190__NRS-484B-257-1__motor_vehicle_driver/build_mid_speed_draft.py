"""Build a fifth, unselected same-traffic 4 m/s sweep candidate for CPU review.

This draft is separate from the delivery manifest. Its offline proof does not
change the four selected cases or claim a completed judgment sweep.
"""

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / 'cases/through_mid'
PREFIX = ROOT.name + '__'
SUFFIX = 'yield_nearest_view_mid_speed'
IDENT = PREFIX + SUFFIX


def replace_once(content, old, new):
    if content.count(old) != 1:
        raise ValueError('Draft patch anchor missing or ambiguous: ' + old)
    return content.replace(old, new)


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    base = json.loads((ROOT / 'construction.json').read_text())
    draft = copy.deepcopy(base)
    draft['case_id'] = IDENT
    by_path = {item['path']: item for item in draft['files']}
    cfg = json.loads(by_path['config.json']['content'])
    cfg['selected_case_id'] = IDENT
    cfg['supported_case_ids'].append(IDENT)
    by_path['config.json']['content'] = json.dumps(cfg, indent=2) + '\n'
    by_path['config.json']['source'] = str((TARGET / 'config.json').relative_to(ROOT.parents[1]))
    (TARGET / 'config.json').write_text(by_path['config.json']['content'])

    controller = by_path['yield_controller.py']
    controller['content'] = replace_once(controller['content'],
        "'yield_nearest_view_no_slow')", "'yield_nearest_view_no_slow',\n                   'yield_nearest_view_mid_speed')")
    controller.pop('source', None)

    runner = by_path['runner.py']
    runner['content'] = replace_once(runner['content'],
        "'yield_nearest_view_clear', 'yield_nearest_view_no_slow')",
        "'yield_nearest_view_clear', 'yield_nearest_view_no_slow',\n            'yield_nearest_view_mid_speed')")
    runner['content'] = replace_once(runner['content'],
        "    if config.get('supported_case_ids') != [PREFIX + suffix for suffix in SUFFIXES]:\n        raise ValueError('Four exact case IDs required')",
        "    supported = [PREFIX + suffix for suffix in SUFFIXES]\n    declared = config.get('supported_case_ids')\n    if case_id == PREFIX + 'yield_nearest_view_mid_speed':\n        valid = declared == supported\n    else:\n        valid = declared in (supported, supported[:-1])\n    if not valid:\n        raise ValueError('Selected case support list differs')")
    runner.pop('source', None)

    for name in ('yield_construction.py', 'finalizer.py'):
        item = by_path[name]
        item['content'] = replace_once(item['content'], 'Stage(case_id)',
            "Stage(case_id, view_speed_mps=4.0 if case_id.endswith('__yield_nearest_view_mid_speed') else 2.0)")
        item.pop('source', None)

    test = '''import json\nimport unittest\nfrom pathlib import Path\nfrom runner import validate_config\nfrom yield_controller import Stage\n\nclass MidSpeedDraftTests(unittest.TestCase):\n    def test_same_traffic_four_mps_target(self):\n        cfg = json.loads(Path(__file__).resolve().parents[1].joinpath("config.json").read_text())\n        validate_config(cfg)\n        stage = Stage(cfg["selected_case_id"], view_speed_mps=4.0)\n        self.assertEqual(stage.target(11.0, within_intersection=False, through_vehicle_clear=False), 4.0)\n        self.assertEqual(stage.target(11.0, within_intersection=False, through_vehicle_clear=True), 4.0)\n        self.assertEqual(stage.target(20.0, within_intersection=False, through_vehicle_clear=False), 6.0)\n\nif __name__ == "__main__":\n    unittest.main()\n'''
    draft['files'].append({'path': 'tests/test_mid_speed.py', 'content': test})
    draft['mechanisms'].append('unselected 4 m/s commanded view target with approaching through actor')
    construction = TARGET / 'construction.json'
    construction.write_text(json.dumps(draft, indent=2) + '\n')
    manifest = {'format': 'worker-execution-manifest-draft', 'assignment_id': ROOT.name,
                'cases': [{'case_id': IDENT,
                           'construction': str(construction.relative_to(ROOT)),
                           'construction_sha256': hashlib.sha256(construction.read_bytes()).hexdigest(),
                           'kind': 'diagnostic_unselected'}],
                'limitation': 'Offline draft only; not in canonical case plan or delivery manifest.'}
    (ROOT / 'mid-speed-draft-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_id': IDENT, 'files': len(draft['files']),
                      'selected_delivery_case': False}))


if __name__ == '__main__':
    main()
