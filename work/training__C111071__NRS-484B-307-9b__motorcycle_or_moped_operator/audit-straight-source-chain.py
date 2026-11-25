"""Independent current-runtime audit of the two straight diagnostic sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
RUNTIME_SOURCE = ROOT / 'runtime/SOURCE-MANIFEST.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def audit():
    source_proof = load(HERE / 'device-antecedents-cpu-proof.json')
    if (not source_proof.get('passed') or source_proof.get('original_native_observed')
            or source_proof.get('physical_detector_causation_verified')):
        raise ValueError('Device diagnostic provenance differs')
    antecedents = {row['case_id']: row for row in source_proof['cases']}
    comparison = load(HERE / 'straight-comparison-proof.json')
    if not comparison.get('passed') or comparison.get('entry_frames') != [250, 150]:
        raise ValueError('Straight controlled comparison differs')
    if comparison.get('original_native_observed') or comparison.get('legal_verdict_claimed'):
        raise ValueError('Straight comparison overclaims provenance')
    cases = {}
    for index, entry in ((1, 250), (2, 150)):
        stem = f'current-v2-probe-{index}'
        case_id = f'{ASSIGNMENT}__probe_{index}'
        native = HERE / f'{stem}-fixture/native_samples.jsonl'
        geometry = HERE / f'{stem}-fixture/road_geometry.json'
        public = HERE / f'{stem}-compatibility.json'
        saved = HERE / f'{stem}-saved-proof.json'
        manifest = HERE / f'{stem}-primary-manifest.json'
        receipt, replay = load(public), load(saved)
        if not receipt.get('passed') or receipt.get('case_id') != case_id:
            raise ValueError('Exact public compatibility case differs')
        if receipt.get('runtime_manifest_sha256') != sha(RUNTIME_SOURCE):
            raise ValueError('Current runtime binding differs')
        if receipt.get('measurement_keys') != ['cycle_requirement', 'detector_trace']:
            raise ValueError('Current straight measurement roster differs')
        antecedent = antecedents.get(case_id)
        if (not antecedent or antecedent['native_samples_sha256'] != sha(native)
                or antecedent['road_geometry_sha256'] != sha(geometry)):
            raise ValueError('Device antecedent source hash differs')
        if antecedent['source_diagnostic']['entry_frame'] != entry:
            raise ValueError('Device antecedent entry differs')
        if comparison['source_sha256'][f'probe_{index}'] != sha(native):
            raise ValueError('Comparison source hash differs')
        for key in ('cycle_requirement', 'detector_trace'):
            sources = receipt['measurement_examples'][key]['sources']
            if sources.get('native_samples.jsonl') != sha(native):
                raise ValueError('Measurement native source hash differs')
            if sources.get('road_geometry.json') != sha(geometry):
                raise ValueError('Measurement road source hash differs')
        detector = receipt['measurement_examples']['detector_trace']['value']
        if detector != {'entry_frame': entry,
                        'detector_request_unserviced_before_entry': True,
                        'physical_failure_cause_verified': False}:
            raise ValueError('Detector source interpretation differs')
        if (not replay.get('passed') or not replay.get('source_hashes_preserved')
                or replay.get('source_files') != 613 or replay.get('original_native_observed')
                or replay.get('selected_delivery')):
            raise ValueError('Recorded-only diagnostic provenance differs')
        if replay.get('compatibility_sha256') != sha(public) or replay.get('manifest_sha256') != sha(manifest):
            raise ValueError('Recorded-only proof binding differs')
        negative = (HERE / f'{stem}-negative-analysis.log').read_text()
        if 'Missing required source: road_geometry.json' not in negative:
            raise ValueError('Missing-road source negative absent')
        cases[case_id] = {'entry_frame': entry, 'native_source_sha256': sha(native),
                          'public_sha256': sha(public), 'saved_sha256': sha(saved)}
    return {'format': 'c111071-straight-source-chain-audit-v1', 'passed': True,
            'assignment_id': ASSIGNMENT, 'cases': cases,
            'comparison_sha256': sha(HERE / 'straight-comparison-proof.json'),
            'device_antecedents_sha256': sha(HERE / 'device-antecedents-cpu-proof.json'),
            'current_runtime_manifest_sha256': sha(RUNTIME_SOURCE),
            'source_kind': 'synthetic_native_shaped_diagnostic',
            'original_native_observed': False, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2, sort_keys=True))
