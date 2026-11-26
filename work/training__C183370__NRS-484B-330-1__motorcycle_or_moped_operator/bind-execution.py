"""Bind selected exact CPU proofs into the canonical execution manifest."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads((ROOT / 'selected-probe-manifest.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    comparisons = []
    for pair in ('ab', 'cd'):
        result = ROOT / 'selected/comparisons' / (pair + '.json')
        log = ROOT / 'selected/comparisons' / (pair + '.log')
        report = json.loads(result.read_text())
        if not report.get('observed_response_difference'):
            raise ValueError('Comparison does not isolate a response change: ' + pair)
        planned = next(item for item in plan['comparisons']
                       if item['case_ids'] == report['case_ids'])
        comparisons.append({'comparison_id': planned['comparison_id'],
                            'case_ids': report['case_ids'],
                            'result': str(result.relative_to(ROOT)),
                            'result_sha256': sha(result),
                            'log': str(log.relative_to(ROOT)),
                            'log_sha256': sha(log)})
    manifest['comparison_audits'] = comparisons
    manifest['status'] = 'selected_native_cpu_proven'
    manifest['delivery_ready'] = False
    for entry in manifest['cases']:
        suffix = entry['case_id'][-1]
        folder = ROOT / 'selected' / ('probe_' + suffix)
        receipt = folder / 'physical-proof/receipt.json'
        entry['physical_preparation'] = {
            'receipt': str(receipt.relative_to(ROOT)), 'sha256': sha(receipt)}
        delivery = folder / 'delivery-proof/receipt.json'
        entry['delivery_acceptance'] = json.loads(delivery.read_text())
        entry['delivery_readiness'] = 'incomplete'
        saved = folder / 'saved-proof/positive-processing.json'
        saved_log = folder / 'saved-proof/positive-saved.log'
        report = json.loads(saved.read_text())
        if (not report.get('passed') or report.get('missing_evidence') or
                not report.get('originals_preserved') or
                report.get('physical_acceptance_claimed') or
                report.get('legal_acceptance_claimed')):
            raise ValueError('Selected saved processing lacks positive source proof')
        entry['post_capture'] = {
            'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' +
                       AID + '/execution-manifest.json --case ' + entry['case_id'] +
                       ' --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT"' +
                       ' --library runtime/library --validator "$VALIDATOR"',
            'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
            'proof': str(saved.relative_to(ROOT)), 'recorded_only': True,
            'test_exit_code': 0, 'test_log': str(saved_log.relative_to(ROOT)),
            'test_log_sha256': sha(saved_log)}
        config = json.loads(next(item['content'] for item in
                                 json.loads((folder / 'construction.json').read_text())['files']
                                 if item['path'] == 'config.json'))
        construction = json.loads((folder / 'construction.json').read_text())
        names = set(config['required_atoms']) | {
            item['name'] for item in construction['recording_description']['channels']}
        evidence = ('native-rows.jsonl, trace.jsonl, video_frames.jsonl, '
                    'capture/evidence.jsonl, capture/native/frames.jsonl and four source videos')
        entry['acquisition'] = {
            name: {'entrypoint': 'runner.py',
                   'method': 'Original Native same-tick actor, signal, geometry and camera capture; source-joined saved measurement',
                   'evidence': evidence} for name in sorted(names)}
    target = ROOT / 'execution-manifest.json'
    target.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest': str(target), 'sha256': sha(target),
                      'selected_cases': len(manifest['cases']),
                      'comparison_audits': len(comparisons)}))


if __name__ == '__main__':
    main()
