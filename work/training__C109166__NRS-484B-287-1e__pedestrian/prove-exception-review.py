"""CPU protocol proof for the NRS 484B.290 source review gate."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from finalize import exception_applicability_measurement


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    outcomes = []
    with tempfile.TemporaryDirectory(dir=HERE.parents[1] / '.runtime-work', prefix='c109166-exception-') as temp:
        folder = Path(temp)
        person = folder / 'pedestrian-original.jsonl'
        person.write_text('{"synthetic_diagnostic":true}\n')
        statute = folder / 'statute-synthetic.txt'
        statute.write_text('Synthetic test source; not NRS text.\n')
        evidence = folder / 'person-synthetic.txt'
        evidence.write_text('Synthetic person evidence; no legal claim.\n')
        source = folder / 'exception-applicability-source.json'
        pending = {'format': 'c109166-exception-applicability-source-v1',
                   'statute': 'NRS 484B.290', 'review_status': 'pending_independent_review',
                   'applicability': 'undetermined', 'synthetic_diagnostic': True}
        write(source, pending)
        assert exception_applicability_measurement(folder)['review_status'] == 'pending_independent_review'
        outcomes.append('pending_source_context_recorded')
        reviewed = {**pending, 'review_status': 'independently_reviewed',
                    'independent_reviewer': 'synthetic CPU protocol test',
                    'exact_statute_source_path': statute.name, 'exact_statute_source_sha256': sha(statute),
                    'pedestrian_original_sha256': sha(person),
                    'person_specific_evidence_path': evidence.name,
                    'person_specific_evidence_sha256': sha(evidence)}
        write(source, reviewed)
        assert exception_applicability_measurement(folder)['applicability'] == 'undetermined'
        outcomes.append('source_hashed_independent_review_recorded')
        for label, bad in (
            ('wrong_statute', {**reviewed, 'statute': 'NRS 484B.287'}),
            ('missing_reviewer', {**reviewed, 'independent_reviewer': ''}),
            ('stale_statute', {**reviewed, 'exact_statute_source_sha256': '0' * 64}),
            ('stale_person', {**reviewed, 'person_specific_evidence_sha256': '0' * 64}),
            ('stale_recording', {**reviewed, 'pedestrian_original_sha256': '0' * 64}),
            ('path_escape', {**reviewed, 'person_specific_evidence_path': '../person-synthetic.txt'})):
            write(source, bad)
            try:
                exception_applicability_measurement(folder)
            except ValueError:
                outcomes.append(label + '_rejected')
            else:
                raise AssertionError(label + ' accepted')
        source.unlink()
        try:
            exception_applicability_measurement(folder)
        except ValueError:
            outcomes.append('missing_exception_source_rejected')
        else:
            raise AssertionError('missing exception source accepted')
    write(HERE / 'exception-review-proof.json', {
        'format': 'c109166-exception-review-cpu-proof-v1', 'outcomes': outcomes,
        'synthetic_diagnostic': True, 'actual_applicability_claimed': False,
        'legal_verdict_claimed': False})
    print(json.dumps({'passed': True, 'outcomes': len(outcomes)}))


if __name__ == '__main__':
    main()
