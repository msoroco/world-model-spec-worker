"""Retain recorded-only taxi fixture receipts and missing-source feedback."""
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c150173-owner'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    cases = []
    for suffix in ('probe_a', 'probe_b', 'probe_c', 'probe_d'):
        stem = ('saved-output-probe_a-v13' if suffix == 'probe_a'
                else f'saved-{suffix}-v13-output')
        source = SCRATCH / stem / 'v0001'
        negative_stem = ('saved-output-probe_a-v13-negative' if suffix == 'probe_a'
                         else f'saved-{suffix}-v13-negative-output')
        negative_source = SCRATCH / negative_stem / 'v0001'
        positive = json.loads((source / 'processing.json').read_text())
        negative = json.loads((negative_source / 'processing.json').read_text())
        feedback = json.loads((negative_source / 'feedback.json').read_text())
        case_id = BASE.name + '__' + suffix
        if (positive.get('case_id') != case_id or negative.get('case_id') != case_id or
                positive.get('passed') is not True or negative.get('passed') is not True or
                positive.get('recorded_only') is not True or
                negative.get('recorded_only') is not True or
                positive.get('originals_preserved') is not True or
                negative.get('originals_preserved') is not True or
                positive.get('missing_evidence') is not False or
                negative.get('missing_evidence') is not True or
                positive['timestamp_joins'].get('frames') != 600 or
                'Missing required source: observed-passenger-activity.jsonl'
                not in feedback.get('error', '')):
            raise ValueError('Taxi recorded-only pair differs: ' + suffix)
        destination = BASE / 'native-selected' / suffix
        files = {}
        for key, path in (
                ('positive_receipt', source / 'processing.json'),
                ('positive_analysis', source / 'analysis.log'),
                ('negative_receipt', negative_source / 'processing.json'),
                ('negative_analysis', negative_source / 'analysis.log'),
                ('negative_feedback', negative_source / 'feedback.json')):
            target = destination / ('saved-' + key.replace('_', '-') + path.suffix)
            target.write_bytes(path.read_bytes())
            files[key] = {'path': str(target.relative_to(BASE)), 'sha256': sha(target)}
        cases.append({'case_id': case_id, 'recorded_only': True,
                      'positive_missing_evidence': False,
                      'negative_missing_evidence': True,
                      'originals_preserved': True, 'files': files})
    output = BASE / 'native-selected' / 'saved-processing-summary.json'
    output.write_text(json.dumps({'format': 'c150173-saved-processing-v1',
                                  'cases': cases}, indent=2) + '\n')
    print(json.dumps({'cases': len(cases), 'summary_sha256': sha(output)}))


if __name__ == '__main__':
    main()
