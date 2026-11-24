"""Independently prove the unselected peak-throttle construction isolation."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'sweep-physical'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def files(path):
    return {row['path']: row['content'] for row in json.loads(path.read_text())['files']}


def check_variant(source_files, variant_files, value):
    if set(source_files) != set(variant_files):
        raise ValueError('Capture file inventory differs')
    expected = "'reference': (0.28, 0.75, 0.92, 0.20)"
    replacement = f"'reference': (0.28, 0.75, {value}, 0.20)"
    if variant_files['runner.py'] != source_files['runner.py'].replace(expected, replacement):
        raise ValueError('Runner changed beyond peak phase')
    source_config = json.loads(source_files['config.json'])
    variant_config = json.loads(variant_files['config.json'])
    if variant_config['control_phases'][2]['throttle'] != value:
        raise ValueError('Requested peak value differs')
    source_config['control_phases'][2]['throttle'] = value
    if source_config != variant_config:
        raise ValueError('Config changed beyond peak phase')
    for name in source_files:
        if name not in ('runner.py', 'config.json') and source_files[name] != variant_files[name]:
            raise ValueError('Measurement or tests changed')
    return variant_config


def main():
    index = json.loads((OUT / 'index.json').read_text())
    if index['frozen_assignment_sha256'] != sha(ROOT / 'inputs' / HERE.name / 'assignment.json'):
        raise ValueError('Frozen assignment changed')
    if index['source_manifest_sha256'] != sha(HERE / 'selected-pair-manifest.json'):
        raise ValueError('Selected construction manifest changed')
    selected = json.loads((HERE / 'selected-pair-manifest.json').read_text())
    source_entry = next(e for e in selected['cases'] if e['case_id'].endswith('__reference'))
    source_path = HERE / source_entry['construction']
    if sha(source_path) != index['source_construction_sha256']:
        raise ValueError('Source construction changed')
    source_files = files(source_path)
    results = []
    for entry in index['entries']:
        tag, value = entry['tag'], entry['value']
        manifest_path = HERE / entry['manifest']
        variant_path = manifest_path.parent / 'construction.json'
        if sha(manifest_path) != entry['manifest_sha256'] or sha(variant_path) != entry['construction_sha256']:
            raise ValueError('Sweep construction reference changed')
        manifest = json.loads(manifest_path.read_text())
        if manifest['cases'][0]['case_id'] != source_entry['case_id'] or manifest['cases'][0]['construction_sha256'] != sha(variant_path):
            raise ValueError('Exact case join differs')
        config = check_variant(source_files, files(variant_path), value)
        if config['duration_s'] != 30 or config['rate_hz'] != 20 or len(config['cameras']) != 4:
            raise ValueError('Capture contract differs')
        if config['control_phases'][2]['first_frame'] != 320 or config['control_phases'][2]['last_frame'] != 439:
            raise ValueError('Peak phase window differs')
        log_source = ROOT / '.runtime-work/c229597-sweep' / ('offline-' + tag) / 'offline.log'
        if not log_source.is_file() or 'OK' not in log_source.read_text():
            raise ValueError('Pinned offline test proof absent')
        log = manifest_path.parent / 'offline.log'
        shutil.copyfile(log_source, log)
        results.append({'tag': tag, 'peak_throttle_request': value,
                        'construction_sha256': sha(variant_path), 'offline_log_sha256': sha(log)})
    variant = files(OUT / index['entries'][0]['tag'] / 'construction.json')
    variant['config.json'] = variant['config.json'].replace('"duration_s": 30', '"duration_s": 10')
    negatives = []
    try:
        check_variant(source_files, variant, index['entries'][0]['value'])
    except ValueError:
        negatives.append('shortened_duration')
    else:
        raise ValueError('Shortened duration accepted')
    variant = files(OUT / index['entries'][0]['tag'] / 'construction.json')
    variant['measure_episode.py'] += '\n# altered\n'
    try:
        check_variant(source_files, variant, index['entries'][0]['value'])
    except ValueError:
        negatives.append('changed_measurement_source')
    else:
        raise ValueError('Changed measurement source accepted')
    report = {'format': 'c229597-peak-throttle-sweep-proof-v1',
              'index_sha256': sha(OUT / 'index.json'),
              'source_construction_sha256': sha(source_path),
              'cases': results, 'negative_rejections': negatives,
              'varied_only': 'requested throttle on frames 320 through 439',
              'source_law': 'LVMC-11-16-090-A',
              'legal_threshold_claimed': False, 'original_native_observed': False,
              'highway_status_reviewed': False, 'delivery_ready': False}
    (OUT / 'proof.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'proof_sha256': sha(OUT / 'proof.json'),
                      'offline_variants': len(results), 'negatives': negatives}))


if __name__ == '__main__':
    main()
