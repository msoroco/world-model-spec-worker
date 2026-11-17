"""Independently check one selected long saved receipt against canonical inputs."""
import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(case_name, candidate, frames, attempt, result_root, summary_path,
          composition_path=None):
    manifest_path = ROOT / 'execution-manifest.json'
    manifest_sha = sha(manifest_path)
    case_id = ROOT.name + '__' + case_name
    entries = [item for item in read(manifest_path)['cases']
               if item['case_id'] == case_id]
    require(len(entries) == 1, 'Unknown selected case')
    entry = entries[0]
    candidates = ([{'id': 'primary',
                    'construction_sha256': entry['construction_sha256']}]
                  + entry['candidates'])
    chosen = [item for item in candidates if item['id'] == candidate]
    require(len(chosen) == 1, 'Unknown selected candidate')
    expected_construction = chosen[0]['construction_sha256']
    attempt = Path(attempt).resolve()
    result_root = Path(result_root).resolve()
    summary_path = Path(summary_path).resolve()
    require(REPO / '.runtime-work' in attempt.parents and
            REPO / '.runtime-work' in result_root.parents and
            summary_path.parent == ROOT,
            'Receipt paths differ from returned/ignored contract')
    result = result_root / 'v0001'
    selection = read(attempt / 'candidate-selection.json')
    summary = read(summary_path)
    processing = read(result / 'processing.json')
    final = read(result / 'final-decode.json')
    require(selection['case_id'] == case_id and
            selection['candidate_id'] == candidate and
            selection['manifest_sha256'] == manifest_sha and
            selection['construction_sha256'] == expected_construction,
            'Candidate selection differs from canonical manifest')
    require(summary['case_id'] == processing['case_id'] == case_id and
            summary['candidate_id'] == processing['candidate_id'] == candidate and
            summary['source_kind'] == 'synthetic_native_sample' and
            summary['passed'] is processing['passed'] is final['passed'] is True and
            summary['frames'] == summary['final_decode_frames'] == frames and
            processing['timestamp_joins']['frames'] == final['frames'] == frames,
            'Saved processing identity, frame join or final decode differs')
    require(summary['source_decodes'] == len(summary['source_decode_sha256']) == 4 and
            summary['originals_preserved'] is processing['originals_preserved'] is True and
            summary['missing_evidence'] is processing['missing_evidence'] is False and
            summary['original_native_observed'] is False and
            summary['physical_acceptance_claimed'] is processing['physical_acceptance_claimed'] is False and
            summary['legal_acceptance_claimed'] is processing['legal_acceptance_claimed'] is False,
            'Saved receipt lacks sources or overclaims acceptance')
    require(processing['analysis_revision']['construction_sha256'] == expected_construction,
            'Saved analysis used another selected construction')
    require(summary['processing_sha256'] == sha(result / 'processing.json') and
            summary['final_decode_sha256'] == sha(result / 'final-decode.json'),
            'Saved processing/final receipt hash differs')
    for index in range(4):
        source = result / ('source-' + str(index) + '.json')
        row = read(source)
        require(summary['source_decode_sha256'][index] == sha(source) and
                row['passed'] is True and row['frames'] == frames,
                'Source camera decode differs: ' + str(index))
    full = REPO / summary['full_log_ignored_path']
    require(REPO / '.runtime-work' in full.resolve().parents and
            summary['full_log_sha256'] == sha(full),
            'Full processing stdout differs')
    if composition_path is None:
        require(summary['composition_mode'] == 'pinned_saved_processing',
                'Unexpected checked composition reuse')
    else:
        composition_path = Path(composition_path).resolve()
        reuse = read(composition_path)
        require(composition_path.parent == ROOT and
                summary['composition_mode'] == 'checked_identical_reuse' and
                summary['reused_composition_receipt_sha256'] == sha(composition_path) and
                reuse['frames'] == frames and
                reuse['reused_identical_synthetic_sources'] is True and
                reuse['composed_sha256'] == sha(attempt / 'raw.mkv'),
                'Checked composition reuse differs')
    return {'format': 'c150142-selected-long-saved-audit-v1',
            'passed': True, 'case_id': case_id, 'candidate_id': candidate,
            'frames': frames, 'manifest_sha256': manifest_sha,
            'construction_sha256': expected_construction,
            'processing_sha256': summary['processing_sha256'],
            'source_kind': 'synthetic_native_sample',
            'original_native_observed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--frames', type=int, required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--result-root', required=True)
    parser.add_argument('--summary', required=True)
    parser.add_argument('--composition-receipt')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.candidate, args.frames,
                           args.attempt, args.result_root, args.summary,
                           args.composition_receipt), indent=2))
