"""Construct source-shaped 86/97 m 300 ft contrast diagnostics."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE = ROOT / 'cases/signal_advance_100_at/build_diagnostic.py'
MANIFEST = ROOT / 'signal-300-sides-draft-manifest.json'
INDEX = ROOT / 'signal-300-sides-draft-index.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    manifest = json.loads(MANIFEST.read_text())
    index = json.loads(INDEX.read_text())
    if len(manifest['cases']) != len(index['cases']) or len(index['cases']) != 2:
        raise ValueError('Two 300 ft companion drafts required')
    results = []
    for entry, indexed in zip(manifest['cases'], index['cases']):
        if entry['case_id'] != indexed['case_id']:
            raise ValueError('Draft manifest and index differ')
        distance = entry['signal_target_m']
        spec = importlib.util.spec_from_file_location('c109749_signal_300_source', SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original_motion = module.motion
        # The selected source yields at frame 145, resumes at 191 and turns at
        # 201. Keep that tail fixed while extending the pre-yield approach.
        target_at_onset = -1.9799999 - distance
        early_step = (-4.46 - target_at_onset) / (144 - 10)

        def motion(index, *, original_motion=original_motion, module=module,
                   target_at_onset=target_at_onset, early_step=early_step):
            row = original_motion(index)
            if index <= 144:
                x = target_at_onset + (index - 10) * early_step
                row['ego'] = module.actor('ego',
                                          (round(x + module.SHIFT_X, 7), module.SHIFT_Y),
                                          (early_step * 20, 0.0))
            row['ego_left_indicator'] = 10 <= index <= 208
            return row

        suffix = entry['case_id'].rsplit('__', 1)[1]
        folder = ROOT / 'cases' / suffix
        module.motion = motion
        module.folder = folder
        module.case = entry['case_id']
        module.build()
        diagnostic = folder / 'diagnostic.json'
        recipe_path = folder / 'diagnostic-recipe.json'
        data = json.loads(diagnostic.read_text())
        provenance = json.loads(data['files']['fixture-provenance.json'])
        provenance['scope'] = (f'210-frame synthetic {distance:.1f} m continuous-signal '
                               'source diagnostic; district, Native motion and legal '
                               'sufficiency unresolved')
        data['files']['fixture-provenance.json'] = json.dumps(provenance, separators=(',', ':')) + '\n'
        diagnostic.write_text(json.dumps(data, separators=(',', ':'), allow_nan=False) + '\n')
        if diagnostic.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Source diagnostic exceeds 2 MiB: ' + suffix)
        source = str(diagnostic.relative_to(REPO))
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json', 'source': source,
                               'sha256': sha(diagnostic)}],
                  'generator': {'source': source, 'sha256': sha(diagnostic)}}
        recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
        entry['fixture_recipe'] = str(recipe_path.relative_to(REPO))
        indexed['diagnostic_sha256'] = sha(diagnostic)
        indexed['recipe_sha256'] = sha(recipe_path)
        from signal_advance_audit import measure
        history = [json.loads(line) for line in data['files']['interaction_history.jsonl'].splitlines()]
        observed = measure(history, probes_m=(91.44,))
        measured = observed['observed_continuous_approach_distance_m']
        if (len(history) != 210 or abs(measured - distance) > .05
                or observed['probes']['91.44']['observable_distance_met'] != (distance >= 91.44)
                or not observed['probes']['91.44']['full_signal_onset_observed']
                or observed['legal_verdict_asserted']):
            raise ValueError('Original-shaped 86/97 m source observation differs')
        results.append({'case_id': entry['case_id'], 'target_m': distance,
                        'observed_m': measured, 'frames': len(history),
                        'diagnostic_sha256': sha(diagnostic),
                        'recipe_sha256': sha(recipe_path),
                        'size_bytes': diagnostic.stat().st_size})
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    INDEX.write_text(json.dumps(index, indent=2) + '\n')
    return {'format': 'worker-signal-300-sides-source-diagnostics',
            'results': results, 'manifest_sha256': sha(MANIFEST),
            'native_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
