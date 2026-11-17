"""Keep complete long saved output ignored and return a small checked receipt."""
import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--frames', type=int, required=True)
    parser.add_argument('--result-root', type=Path, required=True)
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--composition-receipt', type=Path)
    args = parser.parse_args()
    result_root = args.result_root.resolve()
    if REPO / '.runtime-work' not in result_root.parents:
        raise ValueError('Long processing output must be ignored')
    log = args.log.resolve()
    if log.parent != ROOT or not log.is_file():
        raise ValueError('Full processing log must belong to this assignment')
    composition = args.composition_receipt.resolve() if args.composition_receipt else None
    if composition is not None and (composition.parent != ROOT or not composition.is_file()):
        raise ValueError('Missing returned composition source check')
    version = result_root / 'v0001'
    processing = version / 'processing.json'
    final_path = version / 'final-decode.json'
    saved = json.loads(processing.read_text())
    final = json.loads(final_path.read_text())
    sources = [json.loads((version / f'source-{i}.json').read_text())
               for i in range(4)]
    case_id = ROOT.name + '__' + args.case
    if not (saved['case_id'] == case_id and
            saved['candidate_id'] == args.candidate and
            saved['passed'] is True and
            saved['missing_evidence'] is False and
            saved['originals_preserved'] is True and
            saved['timestamp_joins']['frames'] == args.frames and
            saved['final_video_checks']['frames'] == args.frames and
            final['passed'] is True and final['frames'] == args.frames and
            all(row['passed'] is True and row['frames'] == args.frames
                for row in sources) and
            saved['physical_acceptance_claimed'] is False and
            saved['legal_acceptance_claimed'] is False):
        raise ValueError('Selected long saved receipt incomplete')
    full = result_root / f'{args.case}-{args.candidate}-process-saved-full.log'
    if full.exists():
        raise ValueError('Retain existing full log; choose a fresh result root')
    log.rename(full)
    summary = {
        'format': 'c150142-selected-long-saved-summary-v1',
        'case_id': case_id, 'candidate_id': args.candidate,
        'passed': True, 'source_kind': 'synthetic_native_sample',
        'frames': args.frames, 'source_decodes': 4,
        'final_decode_frames': args.frames, 'originals_preserved': True,
        'missing_evidence': False, 'original_native_observed': False,
        'physical_acceptance_claimed': False,
        'legal_acceptance_claimed': False,
        'full_log_ignored_path': full.relative_to(REPO).as_posix(),
        'full_log_sha256': sha(full),
        'processing_ignored_path': processing.relative_to(REPO).as_posix(),
        'processing_sha256': sha(processing),
        'final_decode_sha256': sha(final_path),
        'source_decode_sha256': [sha(version / f'source-{i}.json')
                                 for i in range(4)],
        'composition_mode': ('checked_identical_reuse' if composition is not None
                             else 'pinned_saved_processing'),
    }
    if composition is not None:
        summary['reused_composition_receipt_sha256'] = sha(composition)
    log.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    main()
