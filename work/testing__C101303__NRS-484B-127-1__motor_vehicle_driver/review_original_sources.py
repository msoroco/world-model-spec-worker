"""Independent local inventory of the assigned law and accepted source exports."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
ASSIGNMENT = FOLDER.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    input_root = ROOT / 'inputs' / ASSIGNMENT
    assignment_path = input_root / 'assignment.json'
    evidence_path = input_root / 'evidence.json'
    assignment = json.loads(assignment_path.read_text())
    evidence = json.loads(evidence_path.read_text())
    text = assignment['law']['text']
    terms = ('reasonable and prudent', 'speed of such vehicles',
             'traffic upon', 'condition of the highway')
    if any(term not in text for term in terms):
        raise ValueError('Assigned law judgment factors changed')
    if len(evidence['recordings']) != 8:
        raise ValueError('Expected accepted evidence inventory changed')
    rows = []
    for recording in evidence['recordings']:
        source = recording['sources'][0]
        path = ROOT / source['path']
        if sha(path) != source['sha256']:
            raise ValueError('Accepted metadata hash changed: ' + str(path))
        metadata = json.loads(path.read_text())
        accepted = metadata['acceptance']
        if (accepted['frames'] != 900 or
                metadata['recording_id'] != recording['recording_id'] or
                metadata['reconstruction']['decoder_passed'] is not True):
            raise ValueError('Accepted metadata identity/decoder changed')
        original_trace = Path(accepted['trace_source'])
        rows.append({'case_id': metadata['case_id'],
                     'recording_id': metadata['recording_id'],
                     'metadata_path': source['path'],
                     'metadata_sha256': source['sha256'],
                     'accepted_frames': accepted['frames'],
                     'decoder_passed': True,
                     'original_trace_source': str(original_trace),
                     'original_trace_present_here': original_trace.is_file(),
                     'complete_body_gap_series_in_metadata': False})
    result = {'format': 'c101303-independent-law-source-inventory',
              'law_id': assignment['law_id'], 'law_text': text,
              'law_source': assignment['law']['source'],
              'numeric_legal_following_gap_in_assigned_text': None,
              'judgment_factors': list(terms),
              'selected_branch': assignment['branches'][0]['branch'],
              'accepted_sources': rows,
              'source_sha256': {'assignment': sha(assignment_path),
                                'evidence': sha(evidence_path),
                                'reviewer': sha(Path(__file__))},
              'conclusion': 'Accepted metadata proves inventory and decoder status only. '
                            'It has no complete-body gap series; original actor traces '
                            'must be reviewed before a physical engineering-gap bound.'}
    output = FOLDER / 'independent-law-source-inventory.json'
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'format': result['format'],
                      'accepted_metadata_count': len(rows),
                      'original_traces_present_here': sum(row['original_trace_present_here'] for row in rows),
                      'output_sha256': sha(output)}, sort_keys=True))


if __name__ == '__main__':
    main()
