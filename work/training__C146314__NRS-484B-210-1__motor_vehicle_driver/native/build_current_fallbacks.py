"""Prepare one source-preserving speed-control fallback for each selected case."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
NATIVE = ROOT / 'native'
SOURCE = ROOT / 'draft-selected-execution-manifest.json'
OUTPUT = ROOT / 'preview-fallback-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(SOURCE.read_text())
    candidate_preview = json.loads(json.dumps(manifest))
    for entry, preview_entry in zip(manifest['cases'], candidate_preview['cases']):
        primary = json.loads((ROOT / entry['construction']).read_text())
        candidate = json.loads(json.dumps(primary))
        config_entry = next(item for item in candidate['files'] if item['path'] == 'config.json')
        config = json.loads(config_entry['content'])
        assert config['requested_ego_speed_mps'] == 8.0
        config['requested_ego_speed_mps'] = 8.5
        config['candidate_id'] = 'fallback1'
        config_entry['content'] = json.dumps(config, indent=2, allow_nan=False) + '\n'
        saved_entry = next(item for item in candidate['files'] if item['path'] == 'saved.py')
        old = "report.get('candidate_id') == 'primary'"
        assert old in saved_entry['content']
        saved_entry['content'] = saved_entry['content'].replace(
            old, "report.get('candidate_id') == config['candidate_id']")
        candidate['status'] = 'fallback1_cpu_draft_physical_unverified'
        folder = (ROOT / entry['construction']).parent.parent / 'fallback1'
        folder.mkdir(exist_ok=True)
        path = folder / 'construction.json'
        path.write_text(json.dumps(candidate, indent=2, allow_nan=False) + '\n')
        fallback = {
            'id': 'fallback1',
            'construction': str(path.relative_to(ROOT)),
            'construction_sha256': sha(path),
            'trigger': {'source': 'original Native saved physical-completion feedback',
                        'metric': 'maneuver_completed',
                        'failure_condition': 'Original right-side pass is incomplete after source review'},
            'changed_knobs': ['requested_ego_speed_mps: 8.0 to 8.5 m/s, common to linked cases'],
        }
        entry['candidate_risk'] = {'status': 'physical',
                                   'reason': 'Original right-pass completion is unverified; a small common speed-control adjustment can address an incomplete pass without changing the branch request.'}
        entry['candidates'] = [fallback]
        preview_entry['candidate_risk'] = dict(entry['candidate_risk'])
        preview_entry['candidates'] = [dict(fallback)]
        case_dir = (ROOT / entry['construction']).parent.parent
        fixture_spec = json.loads((case_dir / 'fixture-spec.json').read_text())
        report = json.loads(fixture_spec['files']['native-capture-report.json'])
        report['candidate_id'] = 'fallback1'
        report['config_sha256'] = hashlib.sha256(config_entry['content'].encode()).hexdigest()
        fixture_spec['files']['native-capture-report.json'] = json.dumps(report, indent=2, allow_nan=False) + '\n'
        review = json.loads(fixture_spec['files']['review-source.json'])
        review['capture_report_sha256'] = hashlib.sha256(
            fixture_spec['files']['native-capture-report.json'].encode()).hexdigest()
        fixture_spec['files']['review-source.json'] = json.dumps(review, indent=2, allow_nan=False) + '\n'
        spec_path = folder / 'fixture-spec.json'
        spec_path.write_text(json.dumps(fixture_spec, indent=2, allow_nan=False) + '\n')
        recipe = json.loads((case_dir / 'fixture-recipe.json').read_text())
        recipe['generator']['source'] = str(spec_path.relative_to(REPO))
        recipe['generator']['sha256'] = sha(spec_path)
        recipe_path = folder / 'fixture-recipe.json'
        recipe_path.write_text(json.dumps(recipe, indent=2, allow_nan=False) + '\n')
        preview_entry['fixture_recipe'] = str(recipe_path.relative_to(REPO))
    manifest['status'] = 'selected_fallbacks_construction_draft'
    manifest['delivery_ready'] = False
    OUTPUT.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    (ROOT / 'preview-fallback-compatibility-manifest.json').write_text(
        json.dumps(candidate_preview, indent=2, allow_nan=False) + '\n')
    print('BUILT', len(manifest['cases']), 'exact fallback1 constructions, no physical claim')


if __name__ == '__main__':
    main()
