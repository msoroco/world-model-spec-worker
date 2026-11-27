"""Exercise both exact electric source comparisons on synthetic saved sources."""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, HERE / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    fixture = load('electric_fixture_proof', 'prove-electric-finalize.py').fixture
    audit = load('electric_comparison_audit', 'electric-comparison-audit.py').audit
    reports = []
    for kind in ('electric_bicycle', 'electric_scooter'):
        walk, _ = fixture(kind, 'walk_cycle')
        ride, _ = fixture(kind, 'mounted_sidewalk')
        result = audit(walk, ride, kind)
        assert result['passed'] and not result['physical_acceptance_claimed']
        assert result['machine_class'] == kind
        reports.append(result['comparison_id'])
    walk, _ = fixture('electric_bicycle', 'walk_cycle')
    ride, _ = fixture('electric_scooter', 'mounted_sidewalk')
    try:
        audit(walk, ride, 'electric_bicycle')
    except ValueError as error:
        assert 'class source differs' in str(error), str(error)
    else:
        raise AssertionError('Cross-class comparison accepted')
    walk, _ = fixture('electric_bicycle', 'walk_cycle')
    ride, _ = fixture('electric_bicycle', 'mounted_sidewalk')
    context_path = ride / 'restriction-context.json'
    context = json.loads(context_path.read_text())
    context['sign_text'] = 'CHANGED SIGN'
    context_path.write_text(json.dumps(context) + '\n')
    try:
        audit(walk, ride, 'electric_bicycle')
    except ValueError as error:
        assert 'fixed source condition differs' in str(error), str(error)
    else:
        raise AssertionError('Changed fixed sign accepted')
    walk, _ = fixture('electric_bicycle', 'walk_cycle')
    ride, _ = fixture('electric_bicycle', 'mounted_sidewalk')
    config_path = ride / 'config.json'
    config = json.loads(config_path.read_text())
    config['cameras'][0]['width'] = 64
    config_path.write_text(json.dumps(config) + '\n')
    try:
        audit(walk, ride, 'electric_bicycle')
    except ValueError as error:
        assert 'fixed capture policy differs: cameras' in str(error), str(error)
    else:
        raise AssertionError('Changed fixed camera policy accepted')
    walk, source = fixture('electric_scooter', 'walk_cycle')
    ride, _ = fixture('electric_scooter', 'mounted_sidewalk')
    source.write_text('Changed comparison asset fixture.\n')
    try:
        audit(walk, ride, 'electric_scooter')
    except ValueError as error:
        assert 'asset source changed' in str(error), str(error)
    else:
        raise AssertionError('Stale comparison asset source accepted')
    return {'passed': True, 'fixture_kind': 'synthetic_native_sample',
            'comparison_ids': reports, 'negative_cross_class': True,
            'negative_changed_fixed_sign': True,
            'negative_changed_camera_policy': True,
            'negative_stale_asset_source': True,
            'physical_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
