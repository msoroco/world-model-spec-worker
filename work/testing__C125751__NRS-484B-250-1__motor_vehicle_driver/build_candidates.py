"""Adapt source-bound median-crossing candidates to the exact traffic-light cell.

The prior worker packet is construction material. It does not establish physical
signal state or legal applicability at C125751.
"""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE = REPO / 'work/testing__C125697__NRS-484B-250-1__motor_vehicle_driver'
OLD_ID = SOURCE.name
NEW_ID = ROOT.name
CASES = (
    ('operative_signal_exclusion', 'source_verified_signal_exclusion'),
    ('off_other_enters_first', 'source_verified_off_subsection_4'),
    ('opposite_left_exception', 'source_verified_opposite_intends_left'),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    old_manifest = json.loads((SOURCE / 'execution-manifest.json').read_text())
    cases = []
    for source_suffix, target_suffix in CASES:
        old = next(x for x in old_manifest['cases'] if x['case_id'].endswith('__' + source_suffix))
        source_construction = json.loads((SOURCE / old['construction']).read_text())
        folder = ROOT if target_suffix == CASES[0][1] else ROOT / 'cases' / target_suffix
        folder.mkdir(parents=True, exist_ok=True)
        target_id = NEW_ID + '__' + target_suffix
        proposal = json.loads(json.dumps(source_construction))
        proposal['case_id'] = target_id
        proposal['cell_id'] = 'C125751'
        for item in proposal['files']:
            path = item['path']
            content = item['content']
            if path == 'config.json':
                config = json.loads(content)
                config['cell_id'] = 'C125751'
                config['selected_case_id'] = target_id
                config['supported_case_ids'] = ([NEW_ID + '__' + name for _, name in CASES]
                                                if folder == ROOT else [target_id])
                content = json.dumps(config, indent=2) + '\n'
            elif path.endswith('.py'):
                content = content.replace(OLD_ID, NEW_ID).replace('C125697', 'C125751')
                content = content.replace('__' + source_suffix, '__' + target_suffix)
            # Retain original packet/source-document bytes and their internal
            # hashes. Their C125697 labels disclose the reused candidate.
            target = folder / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            item['content'] = content
            item['source'] = str(target.relative_to(REPO))
        proposal['recording_description'] = json.loads(json.dumps(
            proposal['recording_description']).replace(OLD_ID, NEW_ID)
            .replace('__' + source_suffix, '__' + target_suffix))
        config = json.loads((folder / 'config.json').read_text())
        config['recording_description'] = proposal['recording_description']
        write(folder / 'config.json', config)
        next(x for x in proposal['files'] if x['path'] == 'config.json')['content'] = (
            folder / 'config.json').read_text()
        construction = folder / 'construction.json'
        write(construction, proposal)
        cases.append({'case_id': target_id, 'kind': 'delivery',
                      'construction': str(construction.relative_to(ROOT)),
                      'construction_sha256': sha(construction)})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': NEW_ID,
                'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'cases': cases}
    write(ROOT / 'review-draft-manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    print('built', len(build()), 'candidate cases')
