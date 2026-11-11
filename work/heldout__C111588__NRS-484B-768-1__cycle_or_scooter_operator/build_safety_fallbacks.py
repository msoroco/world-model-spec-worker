"""Three distinct physical-risk fallbacks for both controlled clearance cases."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'first-execution-manifest.json'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


source = json.loads(SOURCE.read_text())['cases'][0]
for slug in ('safety_wide', 'safety_narrow'):
    folder = ROOT / 'cases' / slug
    manifest_path = ROOT / (slug.replace('_', '-') + '-manifest.json')
    manifest = json.loads(manifest_path.read_text())
    entry = manifest['cases'][0]
    primary = json.loads((folder / 'construction.json').read_text())
    entry['candidate_risk'] = {'status': 'physical', 'reason':
        'Native turn route, rider alignment, or source camera visibility may fail while participant offset remains fixed'}
    candidates = []
    for number, original in enumerate(source['candidates'], 1):
        alternate = json.loads(json.dumps(primary))
        files = {row['path']: row for row in alternate['files']}
        if number == 1:
            name, old, new = 'rider_route.py', 'step_m=2.5', 'step_m=1.5'
            assert old in files[name]['content']
            files[name]['content'] = files[name]['content'].replace(old, new)
        elif number == 2:
            for name in ('native_rider_probe.py', 'runner.py'):
                old, new = 'carla.Location(z=.65)', 'carla.Location(z=.85)'
                assert old in files[name]['content']
                files[name]['content'] = files[name]['content'].replace(old, new)
        else:
            name, old, new = 'rider_camera.py', '"driver_reference": ((-2, 0, 1.8)', '"driver_reference": ((-2, 0, 2.2)'
            assert old in files[name]['content']
            files[name]['content'] = files[name]['content'].replace(old, new)
        path = folder / f'fallback{number}-construction.json'
        save(path, alternate)
        candidate = {key: json.loads(json.dumps(value)) for key, value in original.items()
                     if key not in ('offline', 'compatibility')}
        candidate['construction'] = f'cases/{slug}/fallback{number}-construction.json'
        candidate['construction_sha256'] = sha(path)
        candidates.append(candidate)
    entry['candidates'] = candidates
    entry['construction'] = f'cases/{slug}/construction.json'
    entry['measurement_contract'] = f'cases/{slug}/measurement-contract.json'
    entry['construction_sha256'] = sha(folder / 'construction.json')
    entry.pop('physical_preparation', None)
    save(manifest_path, manifest)
    print(slug, 'three fallbacks authored')
