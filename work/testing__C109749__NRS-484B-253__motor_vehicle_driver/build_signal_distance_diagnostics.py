"""Build source-hashed, Native-shaped software diagnostics for 25/36 m probes."""

import hashlib
import importlib.util
import json
import copy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE = ROOT / 'cases/signal_advance_100_at/build_diagnostic.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact(value):
    return json.dumps(value, separators=(',', ':'), allow_nan=False)


def build():
    module_spec = importlib.util.spec_from_file_location('c109749_signal_source', SOURCE)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    original_motion = module.motion
    manifest_path = ROOT / 'signal-distance-draft-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    evidence = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[1]
        distance = entry['signal_target_m']
        onset_index = 54 if distance == 25.0 else 10
        target = ROOT / 'cases' / suffix
        target.mkdir(exist_ok=True)
        def motion(index, *, onset_index=onset_index):
            row = original_motion(index)
            row['ego_left_indicator'] = onset_index <= index <= 208
            return row
        module.motion = motion
        module.folder = target
        module.case = entry['case_id']
        module.build()
        diagnostic = target / 'diagnostic.json'
        spec = json.loads(diagnostic.read_text())
        provenance = json.loads(spec['files']['fixture-provenance.json'])
        provenance['scope'] = (f'210-frame {distance:.1f} m signal-onset software '
                               'diagnostic; no physical or legal acceptance')
        spec['files']['fixture-provenance.json'] = compact(provenance) + '\n'
        diagnostic.write_text(compact(spec) + '\n')
        if diagnostic.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Diagnostic exceeds 2 MiB return limit')
        source = str(diagnostic.relative_to(REPO))
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json', 'source': source,
                               'sha256': sha(diagnostic)}],
                  'generator': {'source': source, 'sha256': sha(diagnostic)}}
        recipe_path = target / 'diagnostic-recipe.json'
        recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
        entry['fixture_recipe'] = str(recipe_path.relative_to(REPO))
        evidence.append({'case_id': entry['case_id'], 'target_m': distance,
                         'onset_index': onset_index, 'diagnostic_sha256': sha(diagnostic),
                         'recipe_sha256': sha(recipe_path),
                         'size_bytes': diagnostic.stat().st_size})
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    template = next(row for row in plan['cases'] if row['case_id'].endswith('__signal_advance_100_at'))
    for entry in manifest['cases']:
        if not any(row['case_id'] == entry['case_id'] for row in plan['cases']):
            row = dict(template)
            row.update(case_id=entry['case_id'],
                       objective=(f'Observe {entry["signal_target_m"]:.1f} m authored signal-onset '
                                  'probe around the 30.48 m reference; Native distance and legal '
                                  'sufficiency remain unverified.'))
            plan['cases'].append(row)
        for disposition in plan['requirement_dispositions']:
            if disposition['status'] == 'selected_required' and entry['case_id'] not in disposition['case_ids']:
                disposition['case_ids'].append(entry['case_id'])
    ids = [ROOT.name + '__signal_advance_100_at'] + [entry['case_id'] for entry in manifest['cases']]
    if not any(row['comparison_id'] == 'signal_advance_100ft_distance_25_30_48_36'
               for row in plan['comparisons']):
        plan['comparisons'].append({
            'comparison_id': 'signal_advance_100ft_distance_25_30_48_36',
            'case_ids': ids,
            'fixed_conditions': ['same selected junction, three actor paths and turn time',
                                 'same 20 Hz, 45-second four-camera capture',
                                 'same signal state after its observed onset'],
            'deliberate_differences': ['authored onset distance 25, 30.48 or 36 m'],
            'source_review_status': 'diagnostic construction only; original Native onset and legal meaning unverified'})
    plan_path.write_text(json.dumps(plan, indent=2) + '\n')
    return evidence


if __name__ == '__main__':
    print(json.dumps({'diagnostics': build(), 'source_kind': 'synthetic software fixture',
                      'physical_or_legal_acceptance_claimed': False}, indent=2))
