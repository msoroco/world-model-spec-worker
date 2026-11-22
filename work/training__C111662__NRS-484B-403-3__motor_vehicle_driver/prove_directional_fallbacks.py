"""Construct and prove six exact shoulder-free intersection fallback probes."""
import concurrent.futures
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from probe_directional_approach import TRANSFORM, TOPOLOGY

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = HERE / 'directional-approach-experiment'
RUN = ROOT / '.runtime-work/c111662-directional-fallbacks'
PYTHON = ROOT / '.venv-cpu/bin/python'
RUNTIME = ROOT / 'runtime.py'
LIBRARY = ROOT / 'runtime/pipeline/library'
VALIDATOR = ROOT / '.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'
CASES = ('reference', 'contrast')
CANDIDATES = ('fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2, sort_keys=True) + '\n')


def command(args, log):
    result = subprocess.run([str(PYTHON), str(RUNTIME), *map(str, args)], cwd=ROOT,
                            capture_output=True, text=True)
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise ValueError(f'CPU command failed ({result.returncode}): {log}: '
                         + (result.stderr or result.stdout)[-900:])


def construct(case, candidate):
    source_manifest = HERE / ('current-16-manifest-' + case + '-' + candidate + '.json')
    manifest = json.loads(source_manifest.read_text())
    entry = manifest['cases'][0]
    ref = next(item for item in entry['candidates'] if item['id'] == candidate)
    construction = json.loads((HERE / ref['construction']).read_text())
    old_road = next(row['content'] for row in construction['files'] if row['path'] == 'road.xodr')
    scope = {}
    exec(TRANSFORM, scope)
    road = scope['directional_approach'](old_road)
    road_sha = hashlib.sha256(road.encode()).hexdigest()
    for item in construction['files']:
        path = item['path']
        if path.endswith('.xodr'):
            item['content'] = road
        elif path.endswith('config.json'):
            config = json.loads(item['content'])
            if 'road_sha256' in config:
                config['road_sha256'] = road_sha
            item['content'] = json.dumps(config, indent=2, sort_keys=True) + '\n'
        elif path.endswith('/native/build.py'):
            item['content'] += ('\n_directional_source_road = road\n' + TRANSFORM +
                                '\ndef road():\n    return directional_approach(_directional_source_road())\n')
        elif path.endswith('/native/check.py'):
            start = item['content'].index('def topology(path):')
            end = item['content'].index('\ndef check(bundle):', start)
            item['content'] = item['content'][:start] + TOPOLOGY + item['content'][end:]
        elif path.endswith('/native/capture.py'):
            item['content'] = item['content'].replace(
                "('west_westbound_outer',403,3,20)",
                "('west_westbound_outer',411,3,20)")
        elif path.endswith('/native/process_original.py'):
            item['content'] = item['content'].replace(
                '"west_westbound_outer": (403, 3)',
                '"west_westbound_outer": (411, 3)')
            item['content'] = item['content'].replace(
                'not in (403, 404, 405, None)',
                'not in (403, 404, 405, 411, None)')
    variant = WORK / case / candidate
    construction_path = variant / 'construction.json'
    write(construction_path, construction)
    ref['construction'] = str(construction_path.relative_to(HERE))
    ref['construction_sha256'] = sha(construction_path)
    entry['preparation_status'] = 'isolated directional approach CPU probe'
    manifest['status'] = 'isolated_directional_approach_fallback_probe'
    manifest_path = HERE / ('directional-approach-' + case + '-' + candidate + '-manifest.json')
    write(manifest_path, manifest)
    return manifest_path, variant, road_sha


def finish(case, candidate, manifest_path, variant, road_sha):
    native = RUN / case / candidate / 'offline' / 'work' / HERE.name / 'native'
    bundle = native / 'selected-draft' / case
    sys.path.insert(0, str(native))
    from saved import make_raw
    raw = make_raw(bundle)
    sys.path.pop(0)
    for module in ('saved', 'build'):
        sys.modules.pop(module, None)
    raw_path = variant / 'raw.json'
    write(raw_path, raw, compact=True)
    original = HERE / 'current-16-experiment' / case / candidate
    diagnostic = json.loads((original / 'diagnostic.json').read_text())
    capture = json.loads(diagnostic['files']['capture/manifest.json'])
    capture['sources']['road.xodr'] = road_sha
    diagnostic['files']['capture/manifest.json'] = json.dumps(capture, indent=2) + '\n'
    diagnostic_path = variant / 'diagnostic.json'
    write(diagnostic_path, diagnostic, compact=True)
    if diagnostic_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Diagnostic exceeds 2 MiB: ' + case + '/' + candidate)
    recipe = json.loads((original / 'recipe.json').read_text())
    diagnostic_ref = str(diagnostic_path.relative_to(ROOT))
    recipe['generator'] = {'source': diagnostic_ref, 'sha256': sha(diagnostic_path)}
    for source in recipe['sources']:
        if source['path'] == 'diagnostic-input.json':
            source.update(source=diagnostic_ref, sha256=sha(diagnostic_path))
        elif source['path'] == 'raw.json':
            source.update(source=str(raw_path.relative_to(ROOT)), sha256=sha(raw_path))
    recipe_path = variant / 'recipe.json'
    write(recipe_path, recipe)
    manifest = json.loads(manifest_path.read_text())
    manifest['cases'][0]['fixture_recipe'] = str(recipe_path.relative_to(ROOT))
    write(manifest_path, manifest)


def prove(case, candidate, manifest_path, variant):
    case_id = HERE.name + '__' + case
    common = ['--manifest', manifest_path, '--case', case_id, '--candidate', candidate]
    output = RUN / case / candidate
    compatibility = output / 'compatibility'
    saved = output / 'saved'
    command(['compatibility', *common, '--output', compatibility,
             '--library', LIBRARY, '--validator', VALIDATOR], variant / 'pinned-compat.log')
    receipt = json.loads((compatibility / 'compatibility.json').read_text())
    if receipt['passed'] is not True or receipt['negative_removed'] != 'raw.json':
        raise ValueError('Positive/negative compatibility failed: ' + case + '/' + candidate)
    command(['process-saved', '--manifest', manifest_path, '--case', case_id,
             '--attempt', compatibility, '--output', saved,
             '--library', LIBRARY, '--validator', VALIDATOR], variant / 'pinned-saved.log')
    processing = json.loads((saved / 'v0001/processing.json').read_text())
    if (processing['passed'] is not True or processing['recorded_only'] is not True or
            processing['originals_preserved'] is not True):
        raise ValueError('Recorded-only saved path failed: ' + case + '/' + candidate)
    for name, source in (('compat-receipt.json', compatibility / 'compatibility.json'),
                         ('saved-receipt.json', saved / 'v0001/processing.json')):
        if source.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Receipt oversized: ' + case + '/' + candidate)
        (variant / name).write_bytes(source.read_bytes())
    return {'case': case, 'candidate': candidate, 'construction_sha256':
            json.loads(manifest_path.read_text())['cases'][0]['candidates'][int(candidate[-1])-1][
                'construction_sha256'], 'receipt_sha256': sha(variant / 'compat-receipt.json'),
            'saved_sha256': sha(variant / 'saved-receipt.json')}


def main():
    tasks = []
    for case in CASES:
        for candidate in CANDIDATES:
            manifest_path, variant, road_sha = construct(case, candidate)
            case_id = HERE.name + '__' + case
            output = RUN / case / candidate / 'offline'
            command(['offline', '--manifest', manifest_path, '--case', case_id,
                     '--candidate', candidate, '--output', output, '--python', PYTHON],
                    variant / 'pinned-offline.log')
            finish(case, candidate, manifest_path, variant, road_sha)
            tasks.append((case, candidate, manifest_path, variant))
    print(json.dumps({'offline_passed': len(tasks)}), flush=True)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(prove, *task) for task in tasks]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            print(json.dumps({'proved': result['case'] + '/' + result['candidate'],
                              'count': len(results)}), flush=True)
    write(WORK / 'fallback-matrix.json', {'format': 'c111662-directional-approach-fallback-matrix-v1',
                                         'cases': sorted(results, key=lambda row:
                                                         (row['case'], row['candidate']))})
    print(json.dumps({'proved': len(results), 'matrix_sha256':
                      sha(WORK / 'fallback-matrix.json')}), flush=True)


if __name__ == '__main__':
    main()
