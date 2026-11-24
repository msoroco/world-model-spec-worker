"""Build source-hashed diagnostic fixtures for the school-warning survey pair."""
import copy
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE / 'crossref-46-native'
TEMPLATE = HERE / 'v2-primary/probe_1'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    manifest_path = HERE / 'crossref-46-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        label = entry['case_id'].split('__crossref_lvmc_11_46_030_', 1)[1]
        out = BASE / label
        source = out / 'fixture-sources'
        source.mkdir(parents=True, exist_ok=True)
        for path in (TEMPLATE / 'sources').rglob('*'):
            if path.is_file() and 'channels' not in path.parts:
                target = source / path.relative_to(TEMPLATE / 'sources')
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
        road = HERE / 'native/road-school-warning-candidate.xodr' if label == 'school_warning_candidate' else HERE / 'native/road.xodr'
        context = json.loads((source / 'curb-context.json').read_text())
        context['authored_road_sha256'] = digest(road)
        context['cross_reference_review'] = {
            'law_id': 'LVMC-11-46-030',
            'school_warning_target_present': label == 'school_warning_candidate',
            'native_lane_and_warning_visibility': 'unverified',
            'original_school_warning_pixels_verified': False,
            'child_context_verified': False,
            'fifty_foot_stop_and_release_verified': False}
        write(source / 'curb-context.json', context)
        capture = json.loads((source / 'capture/manifest.json').read_text())
        capture['sources']['road.xodr'] = digest(road)
        write(source / 'capture/manifest.json', capture)
        generator = copy.deepcopy(json.loads((TEMPLATE / 'generator.json').read_text()))
        write(out / 'generator.json', generator)
        source_items = [{'path': str(path.relative_to(source)),
                         'source': str(path.relative_to(ROOT)), 'sha256': digest(path)}
                        for path in sorted(source.rglob('*')) if path.is_file()]
        write(out / 'recipe.json', {'format': 'worker-fixture-recipe',
              'sources': source_items,
              'generator': {'source': str((out / 'generator.json').relative_to(ROOT)),
                            'sha256': digest(out / 'generator.json')}})
        write(out / 'measurement-contract.json', {
            'format': 'worker-measurement-contract', 'case_id': entry['case_id'],
            'requirements': [{'disposition_index': 0,
                'requirement': 'NRS-484B-283-1b', 'source': 'NRS 484B.283(1)(b)',
                'output_key': 'curb_departure_conditional_margin',
                'method': 'curb_departure', 'value_type': 'object', 'kind': 'measured',
                'inputs': ['curb-samples.jsonl', 'curb-context.json']}],
            'negative': {'remove': ['curb-samples.jsonl'],
                         'error_contains': 'Missing required source: curb-samples.jsonl'}})
        entry['measurement_contract'] = str((out / 'measurement-contract.json').relative_to(HERE))
        entry['measurement_procedure'] = {'entrypoint': 'finalize.py',
                                          'output_schema': 'worker-analysis-report-v1'}
        entry['fixture_recipe'] = str((out / 'recipe.json').relative_to(ROOT))
    write(manifest_path, manifest)
    print(json.dumps({'recipes': len(manifest['cases'])}))


if __name__ == '__main__':
    main()
