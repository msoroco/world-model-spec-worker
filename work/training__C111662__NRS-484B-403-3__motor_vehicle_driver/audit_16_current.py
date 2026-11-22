"""Independently audit the isolated current-runtime 16-candidate CPU matrix."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = HERE / 'current-16-experiment'
RUN = ROOT / '.runtime-work/c111662-16'
CASES = ('reference', 'contrast', 'divided_reference', 'divided_opening')
POLICIES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    runtime_sha = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    recipe_index = read(WORK / 'recipe-index.json')
    construction_index = read(WORK / 'construction-index.json')
    require(recipe_index['runtime_manifest_sha256'] == runtime_sha, 'Recipe index runtime changed')
    require(construction_index['manifest_sha256'] == sha(HERE / 'current-16-experiment-manifest.json'),
            'Construction index manifest changed')
    matrices = {}
    for kind in ('offline', 'compatibility', 'saved'):
        rows = read(RUN / (kind + '-matrix.json'))
        require(len(rows) == 16, kind + ' matrix incomplete')
        matrices[kind] = {(row['case'], row['candidate']): row for row in rows}
        require(len(matrices[kind]) == 16 and all(row['exit_code'] == 0 for row in rows),
                kind + ' matrix failed or duplicated')
    audited = {}
    roads = {}
    comparisons = {}
    for suffix in CASES:
        roads[suffix] = set()
        for candidate in POLICIES:
            key = (suffix, candidate)
            name = suffix + '/' + candidate
            info = recipe_index['variants'][name]
            require(construction_index['variants'][name]['construction_sha256'] ==
                    info['construction_sha256'], 'Construction index disagrees: ' + name)
            variant = WORK / suffix / candidate
            construction_path = variant / 'construction.json'
            recipe_path = variant / 'recipe.json'
            require(sha(construction_path) == info['construction_sha256'] and
                    sha(recipe_path) == info['recipe_sha256'] and
                    sha(variant / 'raw.json') == info['raw_sha256'] and
                    sha(variant / 'diagnostic.json') == info['diagnostic_sha256'],
                    'Source binding changed: ' + name)
            manifest_path = HERE / ('current-16-manifest-' + suffix + '-' + candidate + '.json')
            require(sha(manifest_path) == info['manifest_sha256'], 'Manifest binding changed: ' + name)
            manifest = read(manifest_path)
            require(manifest['runtime_manifest_sha256'] == runtime_sha and len(manifest['cases']) == 1,
                    'Candidate manifest runtime/case mismatch: ' + name)
            entry = manifest['cases'][0]
            ref = entry if candidate == 'primary' else next(
                row for row in entry['candidates'] if row['id'] == candidate)
            require(entry['case_id'].endswith('__' + suffix) and
                    ref['construction_sha256'] == info['construction_sha256'] and
                    ref['construction'] == str(construction_path.relative_to(HERE)) and
                    entry['fixture_recipe'] == str(recipe_path.relative_to(ROOT)),
                    'Exact candidate/recipe binding changed: ' + name)
            recipe = read(recipe_path)
            require(recipe['generator']['sha256'] == sha(ROOT / recipe['generator']['source']) and
                    recipe['generator']['sha256'] == info['diagnostic_sha256'],
                    'Generator binding changed: ' + name)
            for source in recipe['sources']:
                require(source['sha256'] == sha(ROOT / source['source']),
                        'Recipe source changed: ' + name + '/' + source['path'])
            construction = read(construction_path)
            files = {row['path']: row['content'] for row in construction['files']}
            road = next(value for path, value in files.items() if path.endswith('road.xodr'))
            road_sha = hashlib.sha256(road.encode()).hexdigest()
            require(road_sha == info['road_sha256'], 'Road binding changed: ' + name)
            roads[suffix].add(road_sha)
            config = read_config(files, suffix)
            expected_speed = 3.0 if candidate == 'fallback1' else 5.0
            expected_camera = 'elevated_overview' if candidate == 'fallback2' else 'standard'
            expected_dwell = 2.0 if candidate == 'fallback3' else 0.0
            require(config['road_sha256'] == road_sha and config['frames'] == 800 and
                    config['rate_hz'] == 20 and
                    config['requested_approach_speed_mps'] == expected_speed and
                    config['camera_policy'] == expected_camera and
                    config['pre_turn_dwell_s'] == expected_dwell and
                    config['original_native_observed'] is False and
                    config['physical_success_claimed'] is False and
                    config['legal_verdict'] is None,
                    'Candidate policy or provenance changed: ' + name)
            offline = matrices['offline'][key]
            offline_log = ROOT / offline['log']
            require(read(offline_log)['offline_passed'] is True,
                    'Exact offline failed: ' + name)
            comp = matrices['compatibility'][key]
            comp_path = ROOT / comp['output']
            receipt = read(comp_path / 'compatibility.json')
            require(receipt['passed'] is True and receipt['negative_removed'] == 'raw.json' and
                    receipt['case_id'] == entry['case_id'] and
                    receipt['candidate_id'] == candidate and
                    receipt['construction_sha256'] == info['construction_sha256'] and
                    receipt['fixture_recipe_sha256'] == info['recipe_sha256'] and
                    receipt['runtime_manifest_sha256'] == runtime_sha,
                    'Compatibility or negative binding failed: ' + name)
            report_path = comp_path / 'converted/adapter_report.json'
            adapter = read(report_path)
            coverage = adapter['occupancy_coverage']
            require(adapter['frames'] == len(coverage) == 800 and
                    adapter['occupancy_complete'] is True and
                    adapter['atom_coverage']['atoms']['rel.occupies']['passed'] is True and
                    all(not row['incomplete_tracks'] and
                        all(track['complete'] for track in row['tracks']) for row in coverage),
                    'Mandatory occupancy incomplete: ' + name)
            if suffix.startswith('divided_'):
                require(not adapter['native_centre_lines'], 'Divided generated centreline: ' + name)
            saved = matrices['saved'][key]
            saved_path = ROOT / saved['output'] / 'v0001/processing.json'
            processing = read(saved_path)
            require(processing['passed'] is True and processing['recorded_only'] is True and
                    processing['originals_preserved'] is True and
                    processing['physical_acceptance_claimed'] is False and
                    processing['legal_acceptance_claimed'] is False and
                    processing['case_id'] == entry['case_id'] and
                    processing['candidate_id'] == candidate,
                    'Saved processing failed or overclaimed: ' + name)
            evidence = {
                'case_id': entry['case_id'], 'candidate_id': candidate,
                'construction_sha256': info['construction_sha256'],
                'recipe_sha256': info['recipe_sha256'],
                'manifest_sha256': info['manifest_sha256'],
                'road_sha256': road_sha,
                'offline_log_sha256': sha(offline_log),
                'compatibility_log_sha256': sha(ROOT / comp['log']),
                'compatibility_receipt_sha256': sha(comp_path / 'compatibility.json'),
                'adapter_report_sha256': sha(report_path),
                'saved_log_sha256': sha(ROOT / saved['log']),
                'saved_receipt_sha256': sha(saved_path),
                'mandatory_occupancy_frames_complete': len(coverage),
                'measurement_examples': receipt['measurement_examples'],
            }
            for label, source in (
                    ('pinned-offline.log', offline_log),
                    ('pinned-compat.log', ROOT / comp['log']),
                    ('pinned-saved.log', ROOT / saved['log']),
                    ('compat-receipt.json', comp_path / 'compatibility.json'),
                    ('saved-receipt.json', saved_path)):
                require(source.stat().st_size <= 2 * 1024 * 1024,
                        'Returned evidence oversized: ' + name + '/' + label)
                (variant / label).write_bytes(source.read_bytes())
            audited[name] = evidence
            comparisons[key] = receipt['measurement_examples']
        require(len(roads[suffix]) == 1, 'Candidate roads differ: ' + suffix)
    require(roads['reference'] == roads['contrast'] and
            roads['divided_reference'] == roads['divided_opening'],
            'Comparison pairs must share roads')
    for candidate in POLICIES:
        ref = comparisons[('reference', candidate)]
        contrast = comparisons[('contrast', candidate)]
        require(ref['authored_exception_location']['value'] is False and
                contrast['authored_exception_location']['value'] is True and
                44.9 < contrast['turn_crossing_x_m']['value'] -
                ref['turn_crossing_x_m']['value'] < 45.1,
                'Intersection contrast changed: ' + candidate)
        require(comparisons[('divided_reference', candidate)]['authored_divided_opening']['value'] is False and
                comparisons[('divided_opening', candidate)]['authored_divided_opening']['value'] is True,
                'Divided opening contrast changed: ' + candidate)
    proof = {
        'format': 'c111662-current-runtime-isolated-16-chain-audit-v1',
        'status': 'isolated_synthetic_cpu_proof_only',
        'runtime_manifest_sha256': runtime_sha,
        'recipe_index_sha256': sha(WORK / 'recipe-index.json'),
        'construction_index_sha256': sha(WORK / 'construction-index.json'),
        'cases': audited, 'candidate_chains_passed': len(audited),
        'same_policy_comparison_pairs_passed': 8,
        'selected_delivery_proved': False, 'original_native_observed': False,
        'physical_or_legal_acceptance_claimed': False,
        'remaining': 'Review topology/source fidelity, integrate selected manifest, rerun selected exact proofs and independent acceptance/semantic/queue audits before scoped strict readiness.',
    }
    output = WORK / 'current-proof.json'
    output.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'candidate_chains_passed': len(audited),
                      'comparison_pairs_passed': 8, 'proof_sha256': sha(output)}))


def read_config(files, suffix):
    path = 'work/' + HERE.name + '/native/selected-draft/' + suffix + '/config.json'
    return json.loads(files[path])


if __name__ == '__main__':
    main()
