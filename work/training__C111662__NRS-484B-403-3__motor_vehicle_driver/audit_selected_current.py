"""Independently audit current selected C111662 candidate and comparison evidence."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = ('reference', 'contrast', 'divided_reference', 'divided_opening')
POLICIES = ('primary', 'fallback1', 'fallback2', 'fallback3')
EVIDENCE = HERE / 'selected-current-proof'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def original(case, candidate):
    if case in ('reference', 'contrast'):
        base = HERE / 'directional-approach-experiment'
        if candidate == 'primary':
            manifest = HERE / ('directional-approach-experiment-manifest.json' if case == 'reference'
                               else 'directional-approach-contrast-experiment-manifest.json')
            saved = base / ('saved-receipt.json' if case == 'reference' else 'contrast-saved-receipt.json')
        else:
            manifest = HERE / f'directional-approach-{case}-{candidate}-manifest.json'
            saved = base / case / candidate / 'saved-receipt.json'
    else:
        manifest = HERE / f'current-16-manifest-{case}-{candidate}.json'
        saved = HERE / 'current-16-experiment' / case / candidate / 'saved-receipt.json'
    return manifest, saved


def config(construction, case):
    files = {row['path']: row['content'] for row in construction['files']}
    path = f'work/{HERE.name}/native/selected-draft/{case}/config.json'
    road = files['road.xodr']
    return json.loads(files[path]), hashlib.sha256(road.encode()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = read(manifest_path)
    runtime_sha = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    require(manifest['runtime_manifest_sha256'] == runtime_sha, 'Selected runtime changed')
    entries = {entry['case_id'].split('__')[-1]: entry for entry in manifest['cases']}
    require(set(entries) == set(CASES), 'Selected case set changed')
    audited = {}
    comparisons = {}
    roads = {case: set() for case in CASES}
    for case in CASES:
        entry = entries[case]
        for candidate in POLICIES:
            name = case + '/' + candidate
            selected = entry if candidate == 'primary' else next(
                (row for row in entry['candidates'] if row['id'] == candidate), None)
            require(selected is not None, 'Missing selected candidate: ' + name)
            construction_path = HERE / selected['construction']
            require(sha(construction_path) == selected['construction_sha256'],
                    'Selected construction changed: ' + name)
            source_manifest, saved_path = original(case, candidate)
            isolated = read(source_manifest)
            require(isolated['runtime_manifest_sha256'] == runtime_sha and len(isolated['cases']) == 1,
                    'Isolated proof runtime changed: ' + name)
            original_entry = isolated['cases'][0]
            original_ref = original_entry if candidate == 'primary' else next(
                row for row in original_entry['candidates'] if row['id'] == candidate)
            require(original_ref['construction_sha256'] == selected['construction_sha256']
                    and original_ref['construction'] == selected['construction'],
                    'Selected and proved constructions differ: ' + name)
            recipe = ROOT / original_entry['fixture_recipe']
            compatibility = read(EVIDENCE / case / candidate / 'compatibility.json')
            require(compatibility['passed'] is True and compatibility['negative_removed'] == 'raw.json'
                    and compatibility['runtime_manifest_sha256'] == runtime_sha
                    and compatibility['candidate_id'] == candidate
                    and compatibility['case_id'] == entry['case_id']
                    and compatibility['construction_sha256'] == selected['construction_sha256']
                    and compatibility['fixture_recipe_sha256'] == sha(recipe)
                    and selected['compatibility']['sha256'] == sha(EVIDENCE / case / candidate / 'compatibility.json'),
                    'Selected compatibility/source binding failed: ' + name)
            offline = read(EVIDENCE / case / candidate / 'offline.log')
            require(offline['offline_passed'] is True and
                    selected['offline']['log_sha256'] == sha(EVIDENCE / case / candidate / 'offline.log'),
                    'Selected exact offline failed: ' + name)
            saved = read(saved_path)
            require(saved['passed'] is True and saved['recorded_only'] is True
                    and saved['originals_preserved'] is True
                    and saved['physical_acceptance_claimed'] is False
                    and saved['legal_acceptance_claimed'] is False
                    and saved['case_id'] == entry['case_id'] and saved['candidate_id'] == candidate,
                    'Recorded-only saved receipt failed: ' + name)
            construction = read(construction_path)
            settings, road_sha = config(construction, case)
            require(settings['road_sha256'] == road_sha and settings['frames'] == 800
                    and settings['rate_hz'] == 20
                    and settings['requested_approach_speed_mps'] == (3.0 if candidate == 'fallback1' else 5.0)
                    and settings['camera_policy'] == ('elevated_overview' if candidate == 'fallback2' else 'standard')
                    and settings['pre_turn_dwell_s'] == (2.0 if candidate == 'fallback3' else 0.0)
                    and settings['original_native_observed'] is False
                    and settings['physical_success_claimed'] is False
                    and settings['legal_verdict'] is None,
                    'Selected candidate policy or provenance changed: ' + name)
            roads[case].add(road_sha)
            comparisons[name] = compatibility['measurement_examples']
            audited[name] = {'case_id': entry['case_id'], 'candidate_id': candidate,
                             'construction_sha256': selected['construction_sha256'],
                             'isolated_manifest_sha256': sha(source_manifest),
                             'fixture_recipe_sha256': sha(recipe),
                             'compatibility_receipt_sha256': sha(EVIDENCE / case / candidate / 'compatibility.json'),
                             'saved_receipt_sha256': sha(saved_path),
                             'road_sha256': road_sha}
        require(len(roads[case]) == 1, 'Candidate roads differ: ' + case)
    require(roads['reference'] == roads['contrast'] and
            roads['divided_reference'] == roads['divided_opening'],
            'Compared case roads differ')
    for candidate in POLICIES:
        reference = comparisons['reference/' + candidate]
        contrast = comparisons['contrast/' + candidate]
        require(reference['authored_exception_location']['value'] is False
                and contrast['authored_exception_location']['value'] is True
                and 44.9 < contrast['turn_crossing_x_m']['value'] -
                reference['turn_crossing_x_m']['value'] < 45.1,
                'Selected intersection comparison changed: ' + candidate)
        require(comparisons['divided_reference/' + candidate]['authored_divided_opening']['value'] is False
                and comparisons['divided_opening/' + candidate]['authored_divided_opening']['value'] is True,
                'Selected divided comparison changed: ' + candidate)
    proof = {'format': 'c111662-selected-current-cpu-audit-v1',
             'status': 'selected_synthetic_cpu_evidence_only',
             'runtime_manifest_sha256': runtime_sha,
             'selected_manifest_sha256': sha(manifest_path),
             'candidate_chains_bound': len(audited),
             'same_policy_comparison_pairs_passed': 8,
             'cases': audited,
             'original_native_observed': False,
             'physical_or_legal_acceptance_claimed': False,
             'canonical_fallback_recipe_replay_passed': False,
             'remaining': 'Resolve canonical candidate-specific fixture replay, finish delivery and queue checks, then scoped strict.'}
    output = HERE / 'selected-current-proof/selected-audit.json'
    output.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'candidate_chains_bound': len(audited),
                      'same_policy_comparison_pairs_passed': 8,
                      'proof_sha256': sha(output)}))


if __name__ == '__main__':
    main()
