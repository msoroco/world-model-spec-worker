"""Independent exact-bundle and pinned offline receipt audit."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.parent.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    manifest_path = HERE / 'package-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    proof = json.loads((HERE / 'cpu-proof-summary.json').read_text())
    if manifest['assignment_id'] != AID or proof['manifest_sha256'] != sha(manifest_path):
        raise ValueError('Package manifest source differs')
    if proof['physical_success_claimed'] or proof['delivery_ready_claimed']:
        raise ValueError('Unselected CPU proof promoted to readiness')
    proposals = json.loads((HERE / 'proposals/cases.json').read_text())
    if proposals['cell_id'] != 'C111331' or proposals['actor'] != 'motor_vehicle_driver' or proposals['status'] != 'unselected_cpu_draft':
        raise ValueError('Portable proposal identity differs')
    if {p['case_id'] for p in proposals['cases']} != {e['case_id'] for e in manifest['cases']}:
        raise ValueError('Portable proposal cases differ')
    indexed = {(r['case'], r['candidate']): r for r in proof['rows']}
    if len(indexed) != 8 or len(proof['rows']) != 8:
        raise ValueError('Eight exact receipts required')
    source = json.loads((HERE / 'request-summary.json').read_text())
    authored = {(r['case'], r['candidate']): r for r in source['cases']}
    compared = 0
    for case in ('reference', 'contrast'):
        entry = next(e for e in manifest['cases'] if e['case_id'] == AID + '__' + case)
        proposal = next(p for p in proposals['cases'] if p['case_id'] == entry['case_id'])
        if proposal['target_law_id'] != 'NRS-484B-307-6a' or proposal['target_type'] != 'attempt' or proposal['recording_description'] != json.loads((HERE / entry['construction']).read_text())['recording_description']:
            raise ValueError('Portable proposal recording contract differs')
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            ref = entry if candidate == 'primary' else next(c for c in entry['candidates'] if c['id'] == candidate)
            folder = HERE / 'cpu-proofs' / case / candidate
            receipt = indexed[case, candidate]
            construction = HERE / ref['construction']
            selection = json.loads((folder / 'candidate-selection.json').read_text())
            package = json.loads(construction.read_text())
            config = json.loads((folder / 'config.json').read_text())
            if ref['construction_sha256'] != sha(construction) or selection['construction_sha256'] != ref['construction_sha256']:
                raise ValueError('Exact construction hash differs')
            if selection['manifest_sha256'] != sha(manifest_path) or selection['candidate_id'] != candidate:
                raise ValueError('Exact materialized selection differs')
            if receipt['offline_log_sha256'] != sha(folder / 'offline.log') or receipt['materialized_config_sha256'] != sha(folder / 'config.json'):
                raise ValueError('Pinned offline log or config differs')
            if receipt['request_sha256'] != sha(folder / 'native-requests.jsonl') or receipt['request_sha256'] != authored[case, candidate]['request_sha256']:
                raise ValueError('Authored request differs from materialized package')
            if config['authored_config_sha256'] != authored[case, candidate]['config_sha256'] or config['road_sha256'] != source['road_sha256']:
                raise ValueError('Authored config or road source differs')
            if package['status'] != 'unselected_cpu_draft' or config['physical_success_claimed'] or not config['no_native_or_original_observation_claimed']:
                raise ValueError('Draft status or observation boundary differs')
            log = (folder / 'offline.log').read_text()
            if receipt['exit_code'] != 0 or 'Ran 6 tests' not in log or '\nOK\n' not in log or '"carla_imported": false' not in log:
                raise ValueError('Pinned offline and adversarial CPU tests did not pass')
            if candidate != 'primary':
                trigger = ref['trigger']
                if trigger != config['measured_trigger'] or not ref['changed_knobs']:
                    raise ValueError('Fallback trigger or changed knob differs')
            compared += 1
    return {'passed': True, 'exact_bundles': compared, 'negative_cpu_tests_per_bundle': 2,
            'manifest_sha256': sha(manifest_path),
            'offline_summary_sha256': sha(HERE / 'cpu-proof-summary.json'),
            'physical_success_claimed': False, 'delivery_ready_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
