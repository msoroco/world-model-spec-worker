"""Verify terminal reference/contrast selected saved diagnostics."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
EXPECTED = {'reference': {'primary': 119, 'fallback1': 59,
                          'fallback2': 119, 'fallback3': 149},
            'contrast': {'primary': 0, 'fallback1': 0,
                         'fallback2': 0, 'fallback3': 0}}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summarize(case, candidate):
    if case not in EXPECTED or candidate not in EXPECTED[case]:
        raise ValueError('Unknown short saved candidate')
    version = REPO / '.runtime-work' / (
        f'c150142-{case}-{candidate}-update037-saved-result') / 'v0001'
    processing = read(version / 'processing.json')
    final = read(version / 'final-decode.json')
    adapter = read(version / 'converted/adapter_report.json')
    decoder = (version / 'converted/decoder.stdout.log').read_text().strip()
    selected = read(version / 'analysis/candidate-selection.json')
    result = read(version / 'analysis/result.json')
    report = read(version / 'analysis/analysis-report.json')
    sources = sorted(version.glob('source-*.json'))
    case_id = ROOT.name + '__' + case
    expected_hash = sha(ROOT / ('selected-primary' if candidate == 'primary'
                                else 'selected-fallbacks') / case /
                        ('' if candidate == 'primary' else candidate) /
                        'construction.json')
    if (processing['case_id'] != case_id or processing['passed'] is not True or
            processing['candidate_id'] != candidate or
            selected['candidate_id'] != candidate or
            processing['analysis_revision']['construction_sha256'] != expected_hash or
            selected['construction_sha256'] != expected_hash or
            processing['missing_evidence'] is not False or
            processing['originals_preserved'] is not True or
            processing['timestamp_joins']['frames'] != 240 or
            processing['timestamp_joins']['passed'] is not True or
            final['passed'] is not True or final['frames'] != 240 or
            adapter['frames'] != 240 or
            'decoded_frames=240' not in decoder or 'full_core=true' not in decoder or
            len(sources) != 4 or
            any(read(path)['passed'] is not True or read(path)['frames'] != 240
                for path in sources) or
            result['case_id'] != case_id or result['accepted'] is not False or
            result['measured_values']['red_curb_stopped_frames'] !=
            EXPECTED[case][candidate] or
            set(report['measurements']) != {
                'red_curb_stop_or_park_observed', 'red_curb_extent',
                'four_view_frame_join', 'statute_source_context',
                'mail_exception_source_text', 'scope_red_occupancy'}):
        raise ValueError('Incomplete or mismatched short saved proof')
    return {'case_id': case_id, 'candidate_id': candidate, 'passed': True,
            'construction_sha256': expected_hash,
            'processing_sha256': sha(version / 'processing.json'),
            'originals_preserved': True, 'frames': 240,
            'source_decodes': [{'receipt': p.name, 'sha256': sha(p)}
                               for p in sources],
            'adapter_report_sha256': sha(version / 'converted/adapter_report.json'),
            'decoder_stdout': decoder,
            'final_decode_sha256': sha(version / 'final-decode.json'),
            'red_curb_stopped_frames': EXPECTED[case][candidate],
            'original_native_observed': False,
            'output': str(version)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', required=True)
    args = parser.parse_args()
    print(json.dumps(summarize(args.case, args.candidate), sort_keys=True))
