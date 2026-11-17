"""Bind Update053 above-boundary saved receipts to the selected manifest."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ITEMS = {'tour_bus_above': 36122, 'shuttle_bus_above': 36122,
         'limo_above': 36122}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def audit():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest_sha = sha(manifest_path)
    cases = {case['case_id']: case for case in read(manifest_path)['cases']}
    rows = []
    for name, frames in ITEMS.items():
        case_id = ROOT.name + '__' + name
        assert case_id in cases
        summary = read(ROOT / ('update053-' + name.replace('_', '-') +
                               '-selected-primary-saved.log'))
        attempt = REPO / '.runtime-work' / ('c150142-selected-' +
                                             name.replace('_', '-') +
                                             '-primary-native-v1')
        result = REPO / '.runtime-work' / ('c150142-selected-' +
                                            name.replace('_', '-') +
                                            '-primary-result-v1/v0001')
        selection = read(attempt / 'candidate-selection.json')
        processing = read(result / 'processing.json')
        final = read(result / 'final-decode.json')
        assert selection['manifest_sha256'] == manifest_sha
        assert selection['case_id'] == case_id
        assert selection['candidate_id'] == 'primary'
        assert selection['construction_sha256'] == cases[case_id]['construction_sha256']
        assert summary['case_id'] == processing['case_id'] == case_id
        assert summary['candidate_id'] == processing['candidate_id'] == 'primary'
        assert summary['frames'] == frames
        assert summary['source_decodes'] == 4
        assert summary['final_decode_frames'] == final['frames'] == frames
        assert summary['passed'] is processing['passed'] is final['passed'] is True
        assert summary['originals_preserved'] is processing['originals_preserved'] is True
        assert summary['missing_evidence'] is processing['missing_evidence'] is False
        assert summary['physical_acceptance_claimed'] is processing['physical_acceptance_claimed'] is False
        assert summary['legal_acceptance_claimed'] is processing['legal_acceptance_claimed'] is False
        assert processing['timestamp_joins']['frames'] == frames
        assert summary['processing_sha256'] == sha(result / 'processing.json')
        assert summary['final_decode_sha256'] == sha(result / 'final-decode.json')
        assert len(summary['source_decode_sha256']) == 4
        for index in range(4):
            source = result / ('source-' + str(index) + '.json')
            assert summary['source_decode_sha256'][index] == sha(source)
            assert read(source)['frames'] == frames and read(source)['passed'] is True
        rows.append({'case_id': case_id, 'frames': frames,
                     'construction_sha256': selection['construction_sha256'],
                     'processing_sha256': summary['processing_sha256']})
    return {'format': 'c150142-update053-selected-long-audit-v1',
            'passed': True, 'manifest_sha256': manifest_sha,
            'scope': 'synthetic CPU saved processing only', 'rows': rows,
            'original_native_observed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
