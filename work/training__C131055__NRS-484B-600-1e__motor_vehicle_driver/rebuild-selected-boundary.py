"""Refresh selected meter and add source-hashed exact-80 diagnostic case."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ID = HERE.name
LIMIT_MPS = 35.7632


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def source_at():
    old = HERE / 'current-v2-below-sources'
    new = HERE / 'current-v2-at-sources'
    new.mkdir(exist_ok=True)
    for path in old.rglob('*'):
        if path.is_file():
            dest = new / path.relative_to(old)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
    history = new / 'roundabout-speed-history.jsonl'
    rows = [json.loads(line) for line in history.read_text().splitlines()]
    for row in rows:
        row['velocity_xyz_mps'] = [LIMIT_MPS, 0, 0]
    history.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    trace = new / 'trace.jsonl'
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    for row in rows:
        row['velocity_mps'] = [LIMIT_MPS, 0, 0]
        row['speed_mps'] = LIMIT_MPS
        row['speed_mph'] = 80.0
    trace.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    evidence = new / 'capture/evidence.jsonl'
    rows = [json.loads(line) for line in evidence.read_text().splitlines()]
    for row in rows:
        row['ego']['speed_mps'] = LIMIT_MPS
    evidence.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    capture = read(new / 'capture/manifest.json')
    capture['sources']['trace.jsonl'] = sha(trace)
    write(new / 'capture/manifest.json', capture)
    spec = HERE / 'current-v2-at-fixture-spec.json'
    write(spec, read(HERE / 'current-v2-below-fixture-spec.json'))
    recipe = HERE / 'current-v2-at-fixture-recipe.json'
    sources = [{'path': str(path.relative_to(new)),
                'source': str(path.relative_to(ROOT)), 'sha256': sha(path)}
               for path in sorted(new.rglob('*')) if path.is_file()]
    write(recipe, {'format': 'worker-fixture-recipe', 'sources': sources,
                   'generator': {'source': str(spec.relative_to(ROOT)),
                                 'sha256': sha(spec)}})
    contract = read(HERE / 'current-v2-below-measurement-contract.json')
    contract['case_id'] = ID + '__controlled_3'
    contract['requirements'][0]['method'] = 'measure_speed'
    contract['source_bound_boundary'] = {'operator': '>', 'threshold_mps': '35.7632',
                                         'exact_at_request_mps': '35.7632',
                                         'original_measured_speed_unverified': True}
    write(HERE / 'current-v2-at-measurement-contract.json', contract)


def bundled(source, case, candidate):
    source['case_id'] = case
    source['status'] = 'partial_selected_cpu_diagnostic_physical_unverified'
    for item in source['files']:
        if item['path'] in ('runner.py', 'measure.py', 'finalize.py'):
            filename = 'finalize_v2.py' if item['path'] == 'finalize.py' else item['path']
            content = (HERE / 'native' / filename).read_text()
            if item['path'] == 'runner.py' and candidate == 'fallback1':
                old = 'throttle = min(1.0, max(0.0, (target - speed) * .35))'
                assert content.count(old) == 1
                content = content.replace(old, 'throttle = min(1.0, max(0.0, (target - speed) * .55))')
            item['content'] = content
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config.update(case_id=case, selected_case_id=case,
                          supported_case_ids=[case], candidate_id=candidate,
                          case={'case_id': case}, status=source['status'])
            item['content'] = json.dumps(config, sort_keys=True, indent=2) + '\n'
    return source


def main():
    source_at()
    manifest_path = HERE / 'execution-manifest.json'
    manifest = read(manifest_path)
    labels = ('below', 'above', 'at')
    if len(manifest['cases']) != 2:
        raise ValueError('This rebuild expects exactly two prior selected cases')
    for index, label in enumerate(labels, 1):
        case = ID + f'__controlled_{index}'
        if index == 3:
            entry = json.loads(json.dumps(manifest['cases'][0]))
            entry['case_id'] = case
            entry['fixture_recipe'] = str((HERE / 'current-v2-at-fixture-recipe.json').relative_to(ROOT))
            entry['measurement_contract'] = 'current-v2-at-measurement-contract.json'
            entry['construction'] = 'selected-candidates/at/primary/construction.json'
            entry['candidates'][0]['construction'] = 'selected-candidates/at/fallback1/construction.json'
            manifest['cases'].append(entry)
        else:
            entry = manifest['cases'][index - 1]
        for key in ('compatibility', 'negative', 'offline', 'saved_processing',
                    'delivery_diagnostic', 'delivery_acceptance'):
            entry.pop(key, None)
        primary_source = read(HERE / ('selected-candidates/below/primary/construction.json'
                                      if index == 3 else entry['construction']))
        primary_path = HERE / entry['construction']
        write(primary_path, bundled(primary_source, case, 'primary'))
        entry['construction_sha256'] = sha(primary_path)
        entry['preparation_status'] = 'boundary_meter_reproof_pending'
        fallback = entry['candidates'][0]
        for key in ('compatibility', 'negative', 'offline', 'saved_processing',
                    'delivery_diagnostic'):
            fallback.pop(key, None)
        fallback_path = HERE / fallback['construction']
        write(fallback_path, bundled(read(primary_path), case, 'fallback1'))
        fallback['construction_sha256'] = sha(fallback_path)
        fallback['preparation_status'] = 'boundary_meter_reproof_pending'
    manifest['status'] = 'partial_three_case_boundary_meter_reproof_pending'
    for key in ('selected_comparison_diagnostic', 'fallback_isolation_diagnostic',
                'canonical_semantic_local_validation', 'canonical_delivery_local_validation',
                'physical_audit_source_shape_test'):
        manifest.pop(key, None)
    write(manifest_path, manifest)
    print(json.dumps({'manifest_sha256': sha(manifest_path),
                      'selected_construction_sha256': [entry['construction_sha256']
                                                       for entry in manifest['cases']]}))


if __name__ == '__main__':
    main()
