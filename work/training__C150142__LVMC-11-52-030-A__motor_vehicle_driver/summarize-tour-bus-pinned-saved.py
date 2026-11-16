"""Validate and summarize a terminal synthetic tour-bus saved-processing run."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summarize(suffix, version, frames, boundary, activities):
    version = Path(version).resolve()
    if REPO / '.runtime-work' not in version.parents:
        raise ValueError('Pinned synthetic output belongs under .runtime-work')
    case_id = ROOT.name + '__' + suffix
    processing = json.loads((version / 'processing.json').read_text())
    final = json.loads((version / 'final-decode.json').read_text())
    adapter = json.loads((version / 'converted/adapter_report.json').read_text())
    decoder = (version / 'converted/decoder.stdout.log').read_text().strip()
    report = json.loads((version / 'analysis/analysis-report.json').read_text())
    observed = report['measurements']['signed_curb_observation']['value']
    source_paths = sorted(version.glob('source-*.json'))
    sources = [json.loads(path.read_text()) for path in source_paths]
    expected_duration = (frames - 1 - 120) / 20
    if (processing.get('case_id') != case_id or processing.get('passed') is not True
            or processing.get('missing_evidence') is not False
            or processing.get('originals_preserved') is not True
            or processing.get('timestamp_joins', {}).get('frames') != frames
            or processing['timestamp_joins'].get('passed') is not True
            or final.get('passed') is not True or final.get('frames') != frames
            or len(sources) != 4
            or any(s.get('passed') is not True or s.get('frames') != frames
                   for s in sources)
            or adapter.get('frames') != frames
            or f'decoded_frames={frames}' not in decoder
            or 'full_core=true' not in decoder
            or observed.get('duration_relative_to_30_minutes') != boundary
            or abs(observed.get('red_curb_stationary_duration_s', -1)
                   - expected_duration) > 1e-9
            or len(observed.get('recorded_activity_events', [])) != activities
            or observed.get('legal_verdict') is not None
            or observed.get('source_kind') != 'synthetic_native_sample'):
        raise ValueError('Incomplete or mismatched pinned saved-processing proof')
    return {'case_id': case_id, 'source_kind': 'synthetic_native_sample',
            'original_native_observed': False, 'processing_passed': True,
            'processing_sha256': sha(version / 'processing.json'),
            'originals_preserved': True, 'timestamp_join_frames': frames,
            'source_decodes': [{'receipt': path.name, 'sha256': sha(path),
                                'frames': frames, 'passed': True}
                               for path in source_paths],
            'adapter_report_sha256': sha(version / 'converted/adapter_report.json'),
            'decoder_stdout': decoder,
            'final_decode_sha256': sha(version / 'final-decode.json'),
            'final_decode_frames': frames,
            'reported_duration_s': observed['red_curb_stationary_duration_s'],
            'reported_boundary': boundary,
            'reported_activity_events': activities,
            'output': str(version)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--frames', type=int, required=True)
    parser.add_argument('--boundary', required=True)
    parser.add_argument('--activities', type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(summarize(args.case, args.version, args.frames,
                               args.boundary, args.activities), sort_keys=True))
