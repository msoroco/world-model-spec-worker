"""Bind the selected no-countdown context to frozen cited law sources.

This is a planning disposition. It does not decide which exception applies to
an original recording or issue a legal verdict.
"""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAWS = (
    'NRS-484B-287-1c', 'NRS-484B-287-1d', 'NRS-484B-287-1e',
    'NRS-484B-283-1d1', 'LVMC-11-30-140-B', 'LVMC-11-46-030',
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    refs = []
    for law in LAWS:
        matches = list((ROOT / 'inputs').glob(f'*__{law}__*/assignment.json'))
        if len(matches) != 1:
            raise ValueError('Exact cited-law source missing or ambiguous: ' + law)
        path = matches[0]
        source = json.loads(path.read_text())
        if source['law']['id'] != law:
            raise ValueError('Cited-law identity differs: ' + law)
        refs.append({'law_id': law, 'source': path.relative_to(ROOT).as_posix(),
                     'source_sha256': sha(path), 'text': source['law']['text']})
    facts = [
        {'source_law': 'NRS-484B-287-1c',
         'construction_question': 'Are there adjacent device-controlled intersections and is this a marked crosswalk?',
         'required_original_evidence': ['Native map geometry', 'original crosswalk pixels']},
        {'source_law': 'NRS-484B-287-1d',
         'construction_question': 'Is this an intersection diagonal crossing?',
         'required_original_evidence': ['Native pedestrian path', 'Native map geometry']},
        {'source_law': 'NRS-484B-287-1e',
         'construction_question': 'If diagonal movement is authorized, which original device governs it?',
         'required_original_evidence': ['Native path', 'governing head review']},
        {'source_law': 'LVMC-11-30-140-B',
         'construction_question': 'Does the white-cane or assisted blind-person condition arise?',
         'required_original_evidence': ['original pedestrian pixels', 'independent context review']},
        {'source_law': 'LVMC-11-46-030',
         'construction_question': 'Is a school pedestrian lane with a warning device or person involved?',
         'required_original_evidence': ['Native map', 'original lane/device pixels']},
        {'source_law': 'NRS-484B-283-1d1',
         'construction_question': 'Did the pedestrian enter while a governing Walk indication was illuminated?',
         'required_original_evidence': ['pre-entry Native frame history', 'original governing-head pixels']},
    ]
    result = {'format': 'c10316-cited-exception-planning-review-v1',
              'assignment_id': HERE.name, 'source_laws': refs,
              'case_ids': [HERE.name + '__controlled_1', HERE.name + '__controlled_2'],
              'questions': facts, 'disposition': 'measure original applicability per case',
              'new_exception_case_claimed': False,
              'physical_or_legal_conclusion_claimed': False}
    path = HERE / 'exception-review.json'
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(sha(path))


if __name__ == '__main__':
    main()
