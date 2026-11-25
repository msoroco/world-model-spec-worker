"""Independently check both current-runtime 600-frame diagnostic chains."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = ('probe_a', 'probe_b')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def check_case(suffix):
    source = HERE / f'current-v2-{suffix}-source'
    construction = HERE / f'current-v2-{suffix}-diagnostic/construction.json'
    manifest = load(HERE / f'current-v2-{suffix}-diagnostic-manifest.json')
    receipt = load(HERE / f'current-v2-{suffix}-compatibility.json')
    saved = load(HERE / f'current-v2-{suffix}-saved-processing.json')
    case = HERE.name + '__' + suffix
    assert len(manifest['cases']) == 1
    assert manifest['cases'][0]['case_id'] == case
    assert manifest['cases'][0]['construction_sha256'] == sha(construction)
    assert receipt['case_id'] == case and receipt['passed']
    assert receipt['construction_sha256'] == sha(construction)
    assert receipt['candidate_id'] == 'primary'
    assert receipt['log_sha256'] == sha(HERE / f'current-v2-{suffix}-positive.log')
    assert receipt['negative_log_sha256'] == sha(HERE / f'current-v2-{suffix}-negative.log')
    assert receipt['negative_removed'] == 'native_samples.jsonl'
    assert receipt['negative_error_contains'] in (HERE / f'current-v2-{suffix}-negative.log').read_text()
    assert saved['case_id'] == case and saved['passed'] and saved['recorded_only']
    assert saved['candidate_id'] == 'primary' and saved['originals_preserved']
    assert saved['timestamp_joins']['passed'] and saved['timestamp_joins']['frames'] == 600
    assert saved['final_video_checks']['passed'] and saved['final_video_checks']['frames'] == 600
    assert not saved['physical_acceptance_claimed'] and not saved['legal_acceptance_claimed']
    assert saved['analysis_log_sha256'] == sha(HERE / f'current-v2-{suffix}-saved-analysis.log')
    assert saved['original_source_hashes']['native_samples.jsonl'] == sha(source / 'native_samples.jsonl')
    assert saved['original_source_hashes']['road.xodr'] == sha(source / 'road.xodr')
    native = [json.loads(line) for line in (source / 'native_samples.jsonl').read_text().splitlines()]
    trace = [json.loads(line) for line in (source / 'trace.jsonl').read_text().splitlines()]
    assert len(native) == len(trace) == 600
    assert [row['native_frame'] for row in native] == list(range(100, 700))
    assert all(row['ego_actor_id'] == 101 and row['other_actor_id'] == 202 for row in native)
    assert all(row['ego_role'] == 'motor_vehicle_driver' for row in native)
    assert all(math.isclose(row['time_s'], (i + 1) / 20) for i, row in enumerate(native))
    measurement = receipt['measurement_examples']['intersection_approach']['value']
    assert measurement['frames'] == 600 and not measurement['physical_hazard_observed']
    assert not measurement['reduction_necessity_legally_verified']
    fallback_path = HERE / f'current-v2-{suffix}-fallback1-diagnostic/construction.json'
    fallback = load(fallback_path)
    fallback_manifest = load(HERE / f'current-v2-{suffix}-fallback1-diagnostic-manifest.json')
    fallback_entry = fallback_manifest['cases'][0]['candidates'][0]
    fallback_receipt = load(HERE / f'current-v2-{suffix}-fallback1-compatibility.json')
    assert fallback_entry['id'] == 'fallback1'
    assert fallback_entry['construction_sha256'] == sha(fallback_path)
    assert fallback_receipt['candidate_id'] == 'fallback1' and fallback_receipt['passed']
    assert fallback_receipt['construction_sha256'] == sha(fallback_path)
    assert fallback_receipt['log_sha256'] == sha(HERE / f'current-v2-{suffix}-fallback1-positive.log')
    assert fallback_receipt['negative_log_sha256'] == sha(HERE / f'current-v2-{suffix}-fallback1-negative.log')
    assert fallback_receipt['negative_error_contains'] in (HERE / f'current-v2-{suffix}-fallback1-negative.log').read_text()
    offline_log = (HERE / f'current-v2-{suffix}-fallback1-offline.log').read_text()
    assert '"passed": true' in offline_log and offline_log.rstrip().endswith('OK')
    original_config = load_config(load(construction))
    alternate_config = load_config(fallback)
    for key in ('law_id', 'cell_id', 'actor', 'selected_case_id', 'required_atoms',
                'source_packets', 'duration_s', 'rate_hz', 'cameras', 'recording_description'):
        assert original_config[key] == alternate_config[key], key
    return native, measurement, {'case_id': case, 'construction_sha256': sha(construction),
                                 'compatibility_sha256': sha(HERE / f'current-v2-{suffix}-compatibility.json'),
                                 'saved_processing_sha256': sha(HERE / f'current-v2-{suffix}-saved-processing.json'),
                                 'fallback1_construction_sha256': sha(fallback_path),
                                 'fallback1_compatibility_sha256': sha(HERE / f'current-v2-{suffix}-fallback1-compatibility.json'),
                                 'measured_decrease_mph': measurement['measured_decrease_mph']}


def load_config(construction):
    return json.loads(next(f['content'] for f in construction['files'] if f['path'] == 'config.json'))


def main():
    a, ma, pa = check_case('probe_a')
    b, mb, pb = check_case('probe_b')
    assert [r['other_position_m'] for r in a] == [r['other_position_m'] for r in b]
    assert a[0]['ego_position_m'] == b[0]['ego_position_m']
    assert a[0]['ego_velocity_mps'] == b[0]['ego_velocity_mps']
    assert ma['measured_decrease_mph'] > mb['measured_decrease_mph']
    assert ma['measured_relation'] == 'measured_early_decrease_held'
    assert mb['measured_relation'] == 'measured_no_material_decrease'
    proof = {'format': 'c111294-current-v2-diagnostic-audit', 'passed': True,
             'cases': [pa, pb], 'fixed': ['road source', 'initial ego state',
             'other vehicle trajectory', '20 Hz 600-frame acquisition', 'camera profile'],
             'declared_difference': 'ego approach speed profile',
             'limitations': ['synthetic fixtures', 'no original CARLA pixels',
                             'no measured legal necessity or due-care verdict']}
    (HERE / 'current-v2-diagnostic-audit.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed': True, 'cases': len(proof['cases'])}))


if __name__ == '__main__':
    main()
