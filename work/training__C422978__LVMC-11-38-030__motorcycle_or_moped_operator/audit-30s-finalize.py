"""Independently bind six synthetic finalization outputs to saved sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c422978-30s-finalize-v5'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    proof = json.loads((HERE / 'extended-primary/finalization-proof.json').read_text())
    if proof['selected'] or proof['original_native_observed'] or len(proof['positive']) != 6:
        raise ValueError('Finalization proof scope differs')
    for name, digest in proof['media_sha256'].items():
        if sha(ROOT / '.runtime-work/c422978-30s-media' / name) != digest:
            raise ValueError('Synthetic video source hash changed')
    pairs = {}
    for row in proof['positive']:
        case = row['case_id'].rsplit('__', 1)[1]
        candidate = row['candidate_id']
        folder = SCRATCH / (case + '-' + candidate)
        analysis = json.loads((folder / 'analysis-report.json').read_text())
        result = json.loads((folder / 'result.json').read_text())
        source = HERE / 'extended-primary' / case / (
            'construction.json' if candidate == 'primary' else candidate + '/construction.json')
        if (sha(source) != row['construction_sha256'] or
                sha(folder / 'analysis-report.json') != row['analysis_sha256'] or
                sha(folder / 'result.json') != row['result_sha256'] or
                result['case_id'] != row['case_id'] or result['accepted'] is not False or
                result['provenance_kind'] != 'synthetic_local_diagnostic'):
            raise ValueError('Finalization identity or source binding differs')
        measurement = analysis['measurements']['motorcycle_sidewalk_occupancy']
        for name, digest in measurement['sources'].items():
            if sha(folder / name) != digest:
                raise ValueError('Measured original source hash differs')
        for name, digest in proof['media_sha256'].items():
            if sha(folder / name) != digest:
                raise ValueError('Finalized video source hash differs')
        if measurement['value']['moving_sidewalk_overlap_frames'] != row['moving_overlap_frames']:
            raise ValueError('Finalized occupancy differs')
        if len(result['recording_evidence']) != 6 or len(row['channel_sha256']) != 3:
            raise ValueError('Finalized channels or spatial context absent')
        for name, digest in row['channel_sha256'].items():
            path = folder / 'channels' / name
            if sha(path) != digest or len(path.read_text().splitlines()) != 600:
                raise ValueError('Finalized channel source differs')
        pairs.setdefault(candidate, []).append(row['moving_overlap_frames'])
    if pairs != {'primary': [0, 520], 'fallback1': [0, 535], 'fallback3': [0, 520]}:
        raise ValueError('Paired finalization difference changed')
    report = {'format': 'c422978-30s-finalization-independent-audit-v1',
              'finalization_proof_sha256': sha(HERE / 'extended-primary/finalization-proof.json'),
              'cases_audited': 6, 'channel_rows_audited': 10800,
              'paired_overlap_frames': pairs, 'original_native_observed': False,
              'legal_verdict': None}
    output = HERE / 'extended-primary/finalization-audit.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'audit_sha256': sha(output), 'cases': 6}))


if __name__ == '__main__':
    main()
