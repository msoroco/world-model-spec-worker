"""Bind a completed pinned long saved-processing run into a compact proof."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--saved', required=True)
    args = parser.parse_args()
    saved = Path(args.saved).resolve()
    if (REPO / '.runtime-work').resolve() not in saved.parents:
        raise ValueError('Saved source must be in .runtime-work')
    version = saved / 'v0001'
    selected_manifest = HERE / 'execution-manifest.json'
    manifest = json.loads(selected_manifest.read_text())
    case_id = HERE.name + '__' + args.case
    entry = next(e for e in manifest['cases'] if e['case_id'] == case_id)
    processing = json.loads((version / 'processing.json').read_text())
    report = json.loads((version / 'analysis/analysis-report.json').read_text())
    result = json.loads((version / 'analysis/result.json').read_text())
    frames = json.loads((version / 'analysis/config.json').read_text())['capture_frames']
    assert processing['case_id'] == case_id and processing['candidate_id'] == 'primary'
    assert processing['passed'] and processing['recorded_only']
    assert processing['originals_preserved'] and not processing['missing_evidence']
    assert processing['timestamp_joins'] == {'frames': frames, 'passed': True,
                                             'missing_original_trace_or_map': False}
    assert processing['analysis_revision']['construction_sha256'] == entry['construction_sha256']
    assert processing['analysis_revision']['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256']
    assert processing['final_video_checks']['passed'] and processing['final_video_checks']['frames'] == frames
    assert report['source_kind'] == 'synthetic_native_sample'
    assert result['provenance_kind'] == 'synthetic_local_diagnostic'
    source_decodes = {}
    for i in range(4):
        path = version / f'source-{i}.json'
        receipt = json.loads(path.read_text())
        assert receipt['passed'] and receipt['frames'] == frames
        source_decodes[f'source-{i}'] = sha(path)
    proof = {'format': 'c150142-current-selected-long-saved-proof-v1',
             'case_id': case_id, 'candidate_id': 'primary',
             'selected_manifest_sha256': sha(selected_manifest),
             'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
             'processing_sha256': sha(version / 'processing.json'),
             'analysis_report_sha256': sha(version / 'analysis/analysis-report.json'),
             'result_sha256': sha(version / 'analysis/result.json'),
             'source_decode_sha256': source_decodes,
             'final_decode_sha256': sha(version / 'final-decode.json'),
             'source_count': len(processing['original_source_hashes']),
             'source_preserved': True, 'timestamp_joins': processing['timestamp_joins'],
             'final_video': {'passed': True, 'frames': frames,
                             'rgb_sequence_sha256': processing['final_video_checks']['rgb_sequence_sha256']},
             'recorded_only': True, 'synthetic_native_sample': True,
             'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
             'official_public_compatibility_claimed': False}
    output = HERE / f'current-{args.case.replace("_", "-")}-primary-selected-saved-proof.json'
    output.write_text(json.dumps(proof, sort_keys=True, separators=(',', ':')))
    print(json.dumps({'proof': output.name, 'sha256': sha(output), 'frames': frames}, sort_keys=True))


if __name__ == '__main__':
    main()
