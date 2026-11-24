"""Build source-hashed diagnostic packets for the two marked crossing cases."""
import copy
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE / 'crossref-060a-native'
TEMPLATE = HERE / 'v2-primary/probe_1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def put_rows(path, values):
    path.write_text(''.join(json.dumps(value, separators=(',', ':')) + '\n'
                            for value in values))


def main():
    manifest_path = HERE / 'crossref-060a-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        label = entry['case_id'].rsplit('_', 1)[-1]
        y = 0 if label == 'marked' else 4
        out = BASE / label
        source = out / 'fixture-sources'
        source.mkdir(parents=True, exist_ok=True)
        for path in (TEMPLATE / 'sources').rglob('*'):
            if path.is_file() and 'channels' not in path.parts:
                target = source / path.relative_to(TEMPLATE / 'sources')
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
        samples = rows(source / 'curb-samples.jsonl')
        for row in samples:
            row['pedestrian_xy_m'][1] = y
            for vertex in row['pedestrian_footprint_xy_m']:
                vertex[1] += y
        put_rows(source / 'curb-samples.jsonl', samples)
        trace = rows(source / 'trace.jsonl')
        for row in trace:
            row['position']['y'] = y
            row['position_m'][1] = y
        put_rows(source / 'trace.jsonl', trace)
        evidence = rows(source / 'capture/evidence.jsonl')
        for row in evidence:
            row['ego']['position_m'][1] = y
            for vertex in row['ego']['body_vertices_m']:
                vertex[1] += y
        put_rows(source / 'capture/evidence.jsonl', evidence)
        context = json.loads((source / 'curb-context.json').read_text())
        context['authored_road_sha256'] = sha(HERE / 'native/road-crosswalk.xodr')
        context['curb_edge_xy_m'][1] = y
        context['vehicle_conflict_y_m'] = y
        context['cross_reference_review'] = {'law_id': 'LVMC-11-30-060-A',
            'authored_marking_relation': 'inside' if y == 0 else 'outside',
            'actual_paint_pixels': 'unobserved',
            'right_of_way_and_designated_place': 'unreviewed'}
        write(source / 'curb-context.json', context)
        capture = json.loads((source / 'capture/manifest.json').read_text())
        capture['sources']['trace.jsonl'] = sha(source / 'trace.jsonl')
        capture['sources']['road.xodr'] = sha(HERE / 'native/road-crosswalk.xodr')
        write(source / 'capture/manifest.json', capture)
        generator = copy.deepcopy(json.loads((TEMPLATE / 'generator.json').read_text()))
        for graph in generator['graphs']:
            attributes = graph['nodes'][0]['attributes']
            attributes['vertex'][1] = y
            for vertex in attributes['threedbbox']:
                vertex[1] += y
        write(out / 'generator.json', generator)
        source_items = [{'path': str(path.relative_to(source)),
                         'source': str(path.relative_to(ROOT)), 'sha256': sha(path)}
                        for path in sorted(source.rglob('*')) if path.is_file()]
        write(out / 'recipe.json', {'format': 'worker-fixture-recipe',
              'sources': source_items,
              'generator': {'source': str((out / 'generator.json').relative_to(ROOT)),
                            'sha256': sha(out / 'generator.json')}})
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
