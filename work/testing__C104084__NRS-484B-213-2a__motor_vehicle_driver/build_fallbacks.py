"""Bind reviewed alternate crest-anchor selection without changing case capture."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        primary = json.loads((HERE / entry['construction']).read_text())
        alternate = json.loads(json.dumps(primary))
        module = next(item for item in alternate['files'] if item['path'] == 'carla_delegate.py')
        old = "anchor = point(self.carla, setup['crest_anchor'])"
        new = ("require('alternate_crest_anchor' in setup, "
               "'reviewed alternate crest anchor missing')\n"
               "            require(setup['alternate_crest_anchor'] != setup['crest_anchor'], "
               "'alternate crest anchor duplicates primary')\n"
               "            anchor = point(self.carla, setup['alternate_crest_anchor'])")
        if module['content'].count(old) != 1:
            raise ValueError('Native crest-anchor selection changed')
        module['content'] = module['content'].replace(old, new)
        module.pop('source', None)
        alternate['mechanisms'].append('fallback1 requires a distinct source-reviewed alternate crest anchor on the same original map')
        alternate['measurement_plan']['fallback_anchor'] = 'Use original map grade and live four-corner rays at a distinct reviewed anchor; retain exact case and camera contract'
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        target = HERE / f'fallback-{suffix}.json'
        target.write_text(json.dumps(alternate, indent=2, ensure_ascii=False, sort_keys=True) + '\n')
        entry['candidates'] = [{
            'id': 'fallback1', 'construction': target.name,
            'construction_sha256': sha(target),
            'trigger': {'source': 'original road-profile.json and four-view/ray target checks',
                        'metric': 'sampled grade proxy and same-frame four-corner visibility match',
                        'failure_condition': 'primary reviewed anchor does not produce the exact requested blocked or clear view on original frames'},
            'changed_knobs': ['distinct alternate_crest_anchor in reviewed native_setup on the same source-hashed map']
        }]
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
