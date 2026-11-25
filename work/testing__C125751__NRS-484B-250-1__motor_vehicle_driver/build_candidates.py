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
SUFFIX_MAP = dict(CASES)


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
                for old_suffix, new_suffix in SUFFIX_MAP.items():
                    if old_suffix in config:
                        config[new_suffix] = config.pop(old_suffix)
                config['cell_id'] = 'C125751'
                config['selected_case_id'] = target_id
                config['supported_case_ids'] = ([NEW_ID + '__' + name for _, name in CASES]
                                                if folder == ROOT else [target_id])
                content = json.dumps(config, indent=2) + '\n'
            elif path.endswith('.py'):
                content = content.replace(OLD_ID, NEW_ID).replace('C125697', 'C125751')
                for old_suffix, new_suffix in SUFFIX_MAP.items():
                    content = content.replace(old_suffix, new_suffix)
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
        fallback_source = old['candidates'][0]
        fallback = json.loads((SOURCE / fallback_source['construction']).read_text())
        fallback['case_id'] = target_id
        fallback['cell_id'] = 'C125751'
        fallback['recording_description'] = proposal['recording_description']
        for item in fallback['files']:
            path = item['path']
            content = item['content']
            if path == 'config.json':
                config = json.loads(content)
                for old_suffix, new_suffix in SUFFIX_MAP.items():
                    if old_suffix in config:
                        config[new_suffix] = config.pop(old_suffix)
                config['cell_id'] = 'C125751'
                config['selected_case_id'] = target_id
                config['supported_case_ids'] = ([NEW_ID + '__' + name for _, name in CASES]
                                                if folder == ROOT else [target_id])
                config['recording_description'] = proposal['recording_description']
                content = json.dumps(config, indent=2) + '\n'
            elif path.endswith('.py'):
                content = content.replace(OLD_ID, NEW_ID).replace('C125697', 'C125751')
                for old_suffix, new_suffix in SUFFIX_MAP.items():
                    content = content.replace(old_suffix, new_suffix)
            # The fallback is self-contained. Its source documents preserve
            # their original C125697 provenance and pinned hashes.
            item['content'] = content
            item.pop('source', None)
        fallback_path = folder / 'fallback1-construction.json'
        write(fallback_path, fallback)
        cases.append({'case_id': target_id, 'kind': 'delivery',
                      'construction': str(construction.relative_to(ROOT)),
                      'construction_sha256': sha(construction),
                      'measurement_procedure': {'entrypoint': 'finalizer.py'},
                      'measurement_contract': str((folder / 'measurement-contract.json').relative_to(ROOT)),
                      'fixture_recipe': str((folder / 'diagnostic-recipe.json').relative_to(REPO)),
                      'candidate_risk': old['candidate_risk'],
                      'candidates': [{'id': 'fallback1',
                                      'construction': str(fallback_path.relative_to(ROOT)),
                                      'construction_sha256': sha(fallback_path),
                                      'trigger': fallback_source['trigger'],
                                      'changed_knobs': fallback_source['changed_knobs']}]})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': NEW_ID,
                'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'cases': cases}
    write(ROOT / 'review-draft-manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    print('built', len(build()['cases']), 'candidate cases')
