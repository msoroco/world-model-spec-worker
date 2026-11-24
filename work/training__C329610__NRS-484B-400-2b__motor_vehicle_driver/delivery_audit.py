"""Independent exact-case CPU delivery rehearsal; synthetic source is never accepted."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(case_id, diagnostic):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    selected = [e for e in manifest['cases'] if e['case_id'] == case_id]
    if len(selected) != 1:
        raise ValueError('Select one exact case')
    entry = selected[0]
    suffix = case_id.rsplit('__', 1)[-1]
    if not diagnostic:
        raise ValueError('Original Native source required for delivery acceptance')
    source = HERE / 'current-fixture' / suffix
    rows = [json.loads(x) for x in (source / 'native_samples.jsonl').read_text().splitlines()]
    if len(rows) != 480 or any(round(r['time_s'], 3) != round((i + 1) * .05, 3) for i, r in enumerate(rows)):
        raise ValueError('Native body/frame time join incomplete')
    geometry = json.loads((source / 'road_geometry.json').read_text())
    directions = geometry['road_directions_native']
    if (directions['approach_forward'] != [1, 0] or directions['approach_opposing'] != [-1, 0]
            or directions['destination_forward'] != [0, -1]
            or directions['destination_opposing'] != [0, 1]):
        raise ValueError('Both two-directional highways need Native evidence')
    receipt = json.loads((HERE / 'current-public' / (suffix + '-primary-compatibility.json')).read_text())
    processing = json.loads((HERE / 'current-public' / (suffix + '-primary-processing.json')).read_text())
    expected = {'actual_analysis', 'native_validation', 'mandatory_observations',
                'lean_decoder', 'render', 'final_decode', 'four_camera_sources',
                'selected_measurements', 'negative_case_source'}
    if (receipt['case_id'] != case_id or receipt['candidate_id'] != 'primary'
            or receipt['construction_sha256'] != entry['construction_sha256']
            or receipt['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256']
            or not receipt['passed'] or not expected <= set(receipt['checks'])):
        raise ValueError('Current-runtime exact-case compatibility missing')
    if not (processing['passed'] and processing['recorded_only'] and processing['originals_preserved']):
        raise ValueError('Recorded-only saved processing missing')
    physical = json.loads((HERE / entry['physical_preparation']['receipt']).read_text())
    if (sha(HERE / entry['physical_preparation']['receipt']) != entry['physical_preparation']['sha256']
            or physical['original_native_observed'] is not False):
        raise ValueError('Synthetic physical preparation proof changed')
    return {'case_id': case_id, 'diagnostic_only': True, 'physical_acceptance': False,
            'legal_verdict': None, 'source_kind': 'synthetic_fixture',
            'joined_frames': len(rows), 'two_directional_geometry': True,
            'compatibility_sha256': sha(HERE / 'current-public' / (suffix + '-primary-compatibility.json')),
            'saved_processing_sha256': sha(HERE / 'current-public' / (suffix + '-primary-processing.json')),
            'native_samples_sha256': sha(source / 'native_samples.jsonl')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.case, args.diagnostic), sort_keys=True))
