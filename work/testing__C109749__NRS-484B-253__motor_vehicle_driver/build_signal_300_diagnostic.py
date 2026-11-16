"""Build a source-shaped 91.44 m diagnostic for the isolated draft.

The 210-frame motion is synthetic. It retains the selected yield and turn
sequence while lengthening the pre-yield ego approach; no Native realization or
district classification is inferred.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE = ROOT / 'cases/signal_advance_100_at/build_diagnostic.py'
TARGET = ROOT / 'cases/signal_advance_300_at'
MANIFEST = ROOT / 'signal-300-at-draft-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    spec = importlib.util.spec_from_file_location('c109749_300_source', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original_motion = module.motion
    target_at_onset = -93.42
    early_step = (-4.46 - target_at_onset) / (144 - 10)

    def motion(index):
        row = original_motion(index)
        if index <= 144:
            x = target_at_onset + (index - 10) * early_step
            speed = early_step * 20
            row['ego'] = module.actor('ego',
                                       (round(x + module.SHIFT_X, 7), module.SHIFT_Y),
                                       (speed, 0.0))
        row['ego_left_indicator'] = 10 <= index <= 208
        return row

    module.motion = motion
    module.folder = TARGET
    module.case = ROOT.name + '__signal_advance_300_at'
    module.build()
    diagnostic = TARGET / 'diagnostic.json'
    recipe_path = TARGET / 'diagnostic-recipe.json'
    data = json.loads(diagnostic.read_text())
    provenance = json.loads(data['files']['fixture-provenance.json'])
    provenance['scope'] = ('210-frame synthetic 91.44 m continuous-signal source '
                           'diagnostic; district, Native motion and legal sufficiency unresolved')
    data['files']['fixture-provenance.json'] = json.dumps(provenance, separators=(',', ':')) + '\n'
    diagnostic.write_text(json.dumps(data, separators=(',', ':'), allow_nan=False) + '\n')
    if diagnostic.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Source diagnostic exceeds 2 MiB')
    source = str(diagnostic.relative_to(REPO))
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json', 'source': source,
                           'sha256': sha(diagnostic)}],
              'generator': {'source': source, 'sha256': sha(diagnostic)}}
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    manifest = json.loads(MANIFEST.read_text())
    assert len(manifest['cases']) == 1
    manifest['cases'][0]['fixture_recipe'] = source.replace('diagnostic.json', 'diagnostic-recipe.json')
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    from signal_advance_audit import measure
    history = [json.loads(line) for line in data['files']['interaction_history.jsonl'].splitlines()]
    observed = measure(history, probes_m=(91.44,))
    distance = observed['observed_continuous_approach_distance_m']
    if (abs(distance - 91.44) > .05 or not observed['probes']['91.44']['observable_distance_met']
            or not observed['probes']['91.44']['full_signal_onset_observed']
            or observed['legal_verdict_asserted']):
        raise ValueError('91.44 m source observation differs')
    return {'format': 'worker-signal-300-at-source-diagnostic',
            'case_id': module.case, 'frames': len(history),
            'observed_m': distance, 'diagnostic_sha256': sha(diagnostic),
            'recipe_sha256': sha(recipe_path), 'manifest_sha256': sha(MANIFEST),
            'native_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
