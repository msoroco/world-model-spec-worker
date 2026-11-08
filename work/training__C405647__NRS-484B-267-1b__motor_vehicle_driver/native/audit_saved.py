"""Independent recomputation of synthetic saved right-edge proof receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    proof = json.loads((HERE / 'synthetic-saved-proof.json').read_text())
    if proof['processor_sha256'] != sha(HERE / 'measure_saved.py') or proof['manifest_sha256'] != sha(HERE / 'drafts' / 'manifest.json'):
        raise ValueError('saved processor or construction changed')
    expected = {(case, candidate) for case in ('reference', 'contrast')
                for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')}
    if {(p['case'], p['candidate']) for p in proof['positives']} != expected:
        raise ValueError('saved positive case/candidate coverage differs')
    findings = []
    for row in proof['positives']:
        case, candidate = row['case'], row['candidate']
        raw = [json.loads(line) for line in
               (HERE / 'drafts' / case / candidate / 'requested-tracks.jsonl').read_text().splitlines()]
        if len(raw) != 480:
            raise ValueError('construction frame count differs')
        edge = next((i for i, item in enumerate(raw)
                     if item['subject_request']['y_m'] <= -5.95 and
                     item['subject_request']['y_m'] - .9 >= -7), None)
        catchup = next((i for i, item in enumerate(raw)
                        if item['approach_request']['x_m'] >= item['subject_request']['x_m'] - 4.5), None)
        if (edge != row['edge_frame'] or catchup != row['catchup_frame'] or
                (edge is None) != (case == 'contrast')):
            raise ValueError('saved receipt disagrees with raw trajectory')
        findings.append({'case': case, 'candidate': candidate,
                         'edge_frame': edge, 'catchup_frame': catchup})
    negative_names = {item['name'] for item in proof['negatives']}
    if negative_names != {'law_source', 'frame_join', 'native_frame',
                          'coordinate_frame', 'body', 'original_decode'}:
        raise ValueError('saved corruption coverage differs')
    if proof['original_native_processed'] or proof['legal_verdict'] is not None:
        raise ValueError('synthetic proof claims original or legal result')
    receipt = {'format': 'c405647-1b-independent-saved-audit-v1',
               'proof_sha256': sha(HERE / 'synthetic-saved-proof.json'),
               'positives_checked': findings, 'negative_causes_checked': len(negative_names),
               'original_native_processed': False, 'accepted_delivery': False}
    (HERE / 'saved-audit.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
