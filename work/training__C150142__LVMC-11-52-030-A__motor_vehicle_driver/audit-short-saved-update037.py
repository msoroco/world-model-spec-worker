"""Independently audit the current reference and contrast saved paths."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
EXPECTED = {'reference': (119, 59, 119, 149), 'contrast': (0, 0, 0, 0)}
ALLOWED = {'candidate_id', 'risk_trigger', 'tracks_sha256',
           'requested_approach_frames', 'camera_policy'}


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def audit():
    records = {}
    configs = {}
    for case, expected in EXPECTED.items():
        configs[case] = {}
        records[case] = []
        for candidate, stopped in zip(CANDIDATES, expected):
            prefix = f'update037-{case}-{candidate}'
            version = REPO / '.runtime-work' / f'c150142-{case}-{candidate}-update037-saved-result' / 'v0001'
            summary_path = ROOT / f'{prefix}-pinned-saved.json'
            negative_path = ROOT / f'{prefix}-saved-negative.json'
            compatibility_path = ROOT / (f'update037-{case}-primary-compat.json' if candidate == 'primary'
                                         else f'{prefix}-candidate-compat.json')
            summary, negative, compat = map(read, (summary_path, negative_path, compatibility_path))
            processing = read(version / 'processing.json')
            selection = read(version / 'analysis/candidate-selection.json')
            config = read(version / 'analysis/config.json')
            result = read(version / 'analysis/result.json')
            construction = ROOT / ('selected-primary' if candidate == 'primary' else 'selected-fallbacks') / case
            if candidate != 'primary':
                construction /= candidate
            construction_hash = sha(construction / 'construction.json')
            case_id = ROOT.name + '__' + case
            require(summary['passed'] is True and summary['case_id'] == case_id and
                    summary['candidate_id'] == candidate and summary['construction_sha256'] == construction_hash and
                    summary['processing_sha256'] == sha(version / 'processing.json') and
                    summary['frames'] == 240 and len(summary['source_decodes']) == 4 and
                    'decoded_frames=240' in summary['decoder_stdout'] and
                    'full_core=true' in summary['decoder_stdout'] and
                    summary['red_curb_stopped_frames'] == stopped,
                    'Saved path differs: ' + prefix)
            require(processing['passed'] is True and processing['candidate_id'] == candidate and
                    processing['analysis_revision']['construction_sha256'] == construction_hash and
                    selection['construction_sha256'] == construction_hash and
                    selection['candidate_id'] == candidate and processing['originals_preserved'] is True and
                    processing['missing_evidence'] is False and
                    result['accepted'] is False and result['measured_values']['red_curb_stopped_frames'] == stopped,
                    'Selected processing differs: ' + prefix)
            require(negative['rejected'] is True and negative['candidate_id'] == candidate and
                    negative['positive_processing_sha256'] == summary['processing_sha256'] and
                    negative['removed'] == 'native-map-readback.json',
                    'Missing map was accepted: ' + prefix)
            require(compat['passed'] is True and compat['case_id'] == case_id and
                    compat['candidate_id'] == candidate and compat['construction_sha256'] == construction_hash and
                    {'selected_measurements', 'negative_case_source', 'four_camera_sources'} <= set(compat['checks']),
                    'Compatibility differs: ' + prefix)
            require(config['case_id'] == case_id and config['candidate_id'] == candidate,
                    'Scene identity differs: ' + prefix)
            configs[case][candidate] = config
            records[case].append({'candidate_id': candidate,
                                  'summary_sha256': sha(summary_path),
                                  'negative_sha256': sha(negative_path),
                                  'compatibility_sha256': sha(compatibility_path)})
        base = configs[case]['primary']
        for candidate in CANDIDATES[1:]:
            other = configs[case][candidate]
            differences = {key for key in base.keys() | other.keys() if base.get(key) != other.get(key)}
            require(differences <= ALLOWED, 'Fallback changed fixed scene: ' + case + '/' + candidate)
        require(configs[case]['fallback1']['requested_approach_frames'] > base['requested_approach_frames'] and
                configs[case]['fallback2']['camera_policy'] != base['camera_policy'] and
                configs[case]['fallback3']['requested_approach_frames'] < base['requested_approach_frames'] and
                len({configs[case][candidate]['risk_trigger'] for candidate in CANDIDATES[1:]}) == 3,
                'Fallback triggers or mitigations overlap: ' + case)
    for candidate in CANDIDATES:
        reference = configs['reference'][candidate]
        contrast = configs['contrast'][candidate]
        require(reference['case_id'] != contrast['case_id'] and
                reference['candidate_id'] == contrast['candidate_id'] and
                reference['requested_approach_frames'] == contrast['requested_approach_frames'] and
                reference['camera_policy'] == contrast['camera_policy'],
                'Reference/contrast acquisition changed: ' + candidate)
    return {'format': 'c150142-short-saved-audit-v1', 'passed': True,
            'records': records, 'original_native_observed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
